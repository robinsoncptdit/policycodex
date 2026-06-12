"""GitHub App manifest flow.

Standalone — no pre-registered OAuth App needed. The browser POSTs a
manifest JSON to github.com/settings/apps/new, GitHub redirects back
with ?code=<temp>, we exchange the code at
/app-manifests/{code}/conversions and receive App ID, PEM, webhook
secret. Then we auto-pin the test signature so the user can Save
without clicking Test.

Code window: 1 hour, single-use. Three retries on RuntimeError before
showing "Start over."
"""
from __future__ import annotations

import json
import secrets

from django.http import HttpResponse
from django.shortcuts import render

from app.credentials import store
from core.permissions import require_role


_STATE_SESSION_KEY = "github_app_manifest_state"
_RETRY_COUNTER_KEY = "github_app_manifest_retries"
_MAX_RETRIES = 3


def _shell_ctx(panel_title: str) -> dict:
    """Common left-rail + heading context for templates that extend
    base_settings.html outside the normal panel-render path."""
    from app.settings.views import _nav_groups
    return {
        "nav_groups": _nav_groups(),
        "active_slug": "github-app",
        "panel_title": panel_title,
    }


def _build_manifest(redirect_url: str, state_token: str) -> dict:
    return {
        "name": "PolicyCodex",
        "url": "https://policycodex.org",
        "description": "AI-assisted policy management for Catholic dioceses.",
        "public": False,
        "redirect_url": f"{redirect_url}?state={state_token}",
        "default_permissions": {
            "contents": "write",
            "metadata": "read",
            "pull_requests": "write",
            "administration": "write",
        },
        "default_events": [],
    }


def _absolute_callback_url(request) -> str:
    """Return the absolute URL of the manifest-callback view."""
    return request.build_absolute_uri("/settings/github-app/manifest/callback/")


@require_role("Admin")
def manifest_start(request):
    """Render an auto-submitting form that POSTs the manifest to GitHub."""
    state = secrets.token_urlsafe(24)
    request.session[_STATE_SESSION_KEY] = state
    redirect_url = _absolute_callback_url(request)
    manifest = _build_manifest(redirect_url, state)
    return render(request, "settings/panels/_github_app_manifest_form.html", {
        **_shell_ctx("GitHub App — automated setup"),
        "manifest_json": json.dumps(manifest),
        "post_url": "https://github.com/settings/apps/new",
    })


def _exchange_code(code: str) -> dict:
    """POST to GitHub's manifest-conversion endpoint and return the response.
    Caller catches exceptions and decides whether to retry."""
    import requests
    response = requests.post(
        f"https://api.github.com/app-manifests/{code}/conversions",
        headers={"Accept": "application/vnd.github+json"},
        timeout=15,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"GitHub returned {response.status_code}: {response.text[:200]}")
    return response.json()


@require_role("Admin")
def manifest_callback(request):
    """Handle GitHub's redirect after manifest approval."""
    code = request.GET.get("code")
    state = request.GET.get("state")
    expected = request.session.get(_STATE_SESSION_KEY)
    if not state or state != expected:
        return render(request, "settings/panels/_manifest_error.html", {
            **_shell_ctx("GitHub App — setup failed"),
            "error": "State validation failed. Restart the flow.",
            "can_retry": False,
        })
    if not code:
        return render(request, "settings/panels/_manifest_error.html", {
            **_shell_ctx("GitHub App — setup failed"),
            "error": "No code returned by GitHub.",
            "can_retry": False,
        })

    retries = request.session.get(_RETRY_COUNTER_KEY, 0)
    try:
        result = _exchange_code(code)
    except Exception as exc:  # noqa: BLE001
        if retries < _MAX_RETRIES:
            request.session[_RETRY_COUNTER_KEY] = retries + 1
            return render(request, "settings/panels/_manifest_error.html", {
                **_shell_ctx("GitHub App — setup failed"),
                "error": str(exc),
                "can_retry": True,
                "retry_url": request.get_full_path(),
                "retry_count": retries + 1,
            })
        return render(request, "settings/panels/_manifest_error.html", {
            **_shell_ctx("GitHub App — setup failed"),
            "error": f"Failed after {retries} retries: {exc}",
            "can_retry": False,
        })

    # Persist credentials. Installation ID is not in the manifest response
    # (the App is created but not yet installed). User installs next.
    store.set("github_app.app_id", str(result["id"]))
    store.set("github_app.private_key_pem", result["pem"])
    if "webhook_secret" in result:
        store.set("github_app.webhook_secret", result["webhook_secret"])

    # Auto-pin the test signature so Save does not require Test.
    from app.settings.panels.github_app import _signature, _TEST_OK_SESSION_KEY
    # No installation_id yet, but the manual form's signature scheme requires
    # one. Pin with installation_id="" so Save still blocks until the install
    # callback (Task 25) writes the real one.
    sig = _signature(str(result["id"]), "", result["pem"])
    request.session[_TEST_OK_SESSION_KEY] = sig

    # Clear retry counter.
    request.session.pop(_RETRY_COUNTER_KEY, None)
    request.session.pop(_STATE_SESSION_KEY, None)

    # Render the "now install" intermediate page. Use the slug GitHub
    # returned — it appends a -N suffix when "policycodex" is already taken.
    slug = result.get("slug", "policycodex")
    install_url = f"https://github.com/apps/{slug}/installations/new?state={state}"
    return render(request, "settings/panels/_manifest_post_create.html", {
        **_shell_ctx("GitHub App — almost done"),
        "app_id": result["id"],
        "install_url": install_url,
    })


def _list_installations() -> list[dict]:
    """GET /app/installations using a fresh App JWT (10-minute window)."""
    import time
    import jwt as pyjwt
    import requests

    app_id = store.get("github_app.app_id")
    pem = store.get("github_app.private_key_pem")
    now = int(time.time())
    token = pyjwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": str(app_id)},
        pem, algorithm="RS256",
    )
    response = requests.get(
        "https://api.github.com/app/installations",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


@require_role("Admin")
def install_callback(request):
    """User clicked Install on GitHub and was redirected back. Or they
    clicked "I have installed the App" on our post-create page."""
    try:
        installations = _list_installations()
    except Exception as exc:  # noqa: BLE001
        return render(request, "settings/panels/_manifest_error.html", {
            **_shell_ctx("GitHub App — install check failed"),
            "error": f"Could not query installations: {exc}",
            "can_retry": True,
            "retry_url": request.get_full_path(),
            "retry_count": 1,
        })

    if not installations:
        # User may have approved but the install API has not propagated yet.
        return render(request, "settings/panels/_install_pending.html", {
            **_shell_ctx("GitHub App — waiting for installation"),
            "retry_url": request.get_full_path(),
        })

    # Pick the most recent installation. With multiple, latest by ID (which
    # is monotonically increasing). The diocese will typically have one.
    latest = max(installations, key=lambda i: i["id"])
    store.set("github_app.installation_id", str(latest["id"]))

    # Re-pin the signature now that we have the full triplet so Save needs
    # no Test click.
    from app.settings.panels.github_app import _signature, _TEST_OK_SESSION_KEY
    sig = _signature(
        store.get("github_app.app_id"),
        store.get("github_app.installation_id"),
        store.get("github_app.private_key_pem"),
    )
    request.session[_TEST_OK_SESSION_KEY] = sig

    from django.shortcuts import redirect
    return redirect("settings_panel", slug="github-app")
