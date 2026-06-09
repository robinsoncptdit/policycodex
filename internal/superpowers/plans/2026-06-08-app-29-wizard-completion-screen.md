# APP-29 Wizard Completion Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the post-onboarding `redirect("catalog")` with a presentation-only completion screen that walks the diocese admin through the publish sequence (merge the config PR, configure GitHub Pages, set the registrar CNAME).

**Architecture:** A new GET-able Django view (`onboarding_complete`) at URL name `onboarding-complete`, rendering `onboarding/complete.html` in the APP-28 DaisyUI/Inter vocabulary. It derives the org/repo from existing wizard state (`github-repo` step) and reads a best-effort PR url the accept handlers stash in the session. Both onboarding accept exit points (the full-page `handle()` path and the HTMX `_do_accept` path) stop redirecting to the catalog, stash the PR url in the session, and redirect to the new screen. No API calls, no commits, no GitHub Pages API.

**Tech Stack:** Django 6 (views, URL routing, sessions), HTMX (`HX-Redirect` for full-page nav from a fragment), Tailwind + DaisyUI templates, pytest-django.

**Test interpreter:** `ai/venv/bin/python -m pytest` (no root venv; system python lacks pytest).

**Spec:** `internal/superpowers/specs/2026-06-08-app-29-wizard-completion-screen-design.md`

---

## File Structure

- **Create** `app/onboarding/templates/onboarding/complete.html` — the completion screen markup (heading, ordered 1-2-3 checklist, copy button, continue button, HOWTO footer link). Presentation only.
- **Modify** `app/onboarding/views.py` — add `_derive_repo(state)` helper + `onboarding_complete` GET view.
- **Modify** `app/onboarding/urls.py` — register `complete/` **before** the catch-all `<slug:step>/` route.
- **Modify** `app/onboarding/retention_policy.py` — rewire both accept exits (plain-POST at the `handle()` accept branch ~line 214-220; HTMX `_do_accept` ~line 349-355) to stash `onboarding_pr_url` in the session and redirect to `onboarding-complete`; drop the two `messages.success(...)` toasts.
- **Create** `app/onboarding/tests/test_onboarding_complete.py` — tests for the new view (connect/create render, pr_url present/absent, guard).
- **Modify** `app/onboarding/tests/test_onboarding_views.py` — update 3 existing accept tests that assert `/catalog/`.
- **Modify** `app/onboarding/tests/test_screen7_htmx.py` — update the HTMX accept test that asserts `HX-Redirect == reverse("catalog")`.

## Key reconciliations with the spec (read before starting)

1. **HTMX accept returns 204, not 200.** The existing helper `retention_policy._hx_redirect(url)` returns `HttpResponse(status=204)` with an `HX-Redirect` header. Reuse it: `return _hx_redirect(reverse("onboarding-complete"))`. Tests assert status 204.
2. **URL ordering is load-bearing.** `app/onboarding/urls.py` ends with a catch-all `path("<slug:step>/", views.onboarding_step, ...)`. A request to `/onboarding/complete/` would otherwise be captured as `step="complete"` and 404 in `onboarding_step`. The new `complete/` path MUST be registered before that catch-all.
3. **Wizard state survives accept.** The accept handlers call `state.mark_complete(STEP_SLUG)` but never reset wizard state, so `state.get_data("github-repo")` is still readable on the completion screen. The bundle staging dir is `rmtree`d, but session wizard data is not.
4. **`pr_url` is popped (best-effort).** The view does `request.session.pop("onboarding_pr_url", None)`. On a page refresh the PR link is gone; step 1 then shows plain instruction text. This is the approved design — do not change it.

---

## Task 1: Completion view, URL, and template

**Files:**
- Create: `app/onboarding/tests/test_onboarding_complete.py`
- Modify: `app/onboarding/views.py`
- Modify: `app/onboarding/urls.py`
- Create: `app/onboarding/templates/onboarding/complete.html`

- [ ] **Step 1: Write the failing tests**

Create `app/onboarding/tests/test_onboarding_complete.py`:

```python
"""Tests for the onboarding completion screen (APP-29).

A presentation-only GET view. It derives org/repo from the screen-1
`github-repo` wizard data and reads a best-effort PR url the accept handlers
stash in the session. No network, no git, no AI.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


def _seed_connect(client):
    """Populate screen-1 wizard data via the real form post (connect mode)."""
    client.post(
        "/onboarding/github-repo/",
        {
            "action": "continue",
            "mode": "connect",
            "repo_url": "https://github.com/acme/policies",
            "branch": "main",
        },
    )


def _seed_create(client):
    client.post(
        "/onboarding/github-repo/",
        {
            "action": "continue",
            "mode": "create",
            "org": "acme",
            "repo_name": "policies",
            "branch": "main",
        },
    )


def test_connect_mode_renders_derived_links(client, user, settings):
    settings.POLICYCODEX_SOURCE_URL = "https://github.com/policycodex/policycodex"
    client.force_login(user)
    _seed_connect(client)
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "https://github.com/acme/policies/settings/pages" in body
    assert "acme.github.io" in body
    assert 'data-copy="acme.github.io"' in body
    assert (
        "https://github.com/policycodex/policycodex/blob/main/"
        "HOWTO-GitHub-Team-Setup.md" in body
    )
    assert reverse("catalog") in body  # the continue button target


def test_create_mode_renders_derived_links(client, user):
    client.force_login(user)
    _seed_create(client)
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "https://github.com/acme/policies/settings/pages" in body
    assert "acme.github.io" in body


def test_pr_url_present_renders_pr_link(client, user):
    client.force_login(user)
    _seed_connect(client)
    session = client.session
    session["onboarding_pr_url"] = "https://github.com/acme/policies/pull/1"
    session.save()
    resp = client.get(reverse("onboarding-complete"))
    body = resp.content.decode()
    assert "https://github.com/acme/policies/pull/1" in body


def test_pr_url_absent_renders_no_broken_anchor(client, user):
    client.force_login(user)
    _seed_connect(client)
    resp = client.get(reverse("onboarding-complete"))
    body = resp.content.decode()
    assert "/pull/" not in body  # no PR anchor when none was stashed


def test_guard_redirects_when_no_repo_data(client, user):
    client.force_login(user)
    # No github-repo wizard data seeded.
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 302
    assert resp.url == reverse("onboarding")


def test_unauthenticated_redirects_to_login(client, db):
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_complete.py -v`
Expected: FAIL — `reverse("onboarding-complete")` raises `NoReverseMatch` (URL not registered yet).

- [ ] **Step 3: Add the URL route (before the catch-all)**

In `app/onboarding/urls.py`, insert the `complete/` path BEFORE the `<slug:step>/` catch-all:

```python
"""URL routes for the onboarding wizard (APP-08)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.onboarding_root, name="onboarding"),
    path("complete/", views.onboarding_complete, name="onboarding-complete"),
    path("<slug:step>/", views.onboarding_step, name="onboarding_step"),
]
```

- [ ] **Step 4: Add the derivation helper + view**

In `app/onboarding/views.py`, add `from django.conf import settings` to the imports, and a `from urllib.parse import urlparse` at the top. Then add the helper and view (place after `onboarding_step`):

```python
def _derive_repo(state):
    """Return (org, repo) from the screen-1 github-repo wizard data, or None.

    connect mode parses the repo_url; create mode reads org + repo_name.
    Returns None when the data is missing or org/repo cannot be derived, so
    the completion view can guard instead of rendering a half-empty screen.
    """
    data = state.get_data("github-repo") or {}
    mode = data.get("mode")
    if mode == "connect":
        path = urlparse(data.get("repo_url") or "").path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None
        org, repo = parts[0], parts[1].removesuffix(".git")
    elif mode == "create":
        org, repo = data.get("org"), data.get("repo_name")
    else:
        return None
    if not org or not repo:
        return None
    return org, repo


@login_required
def onboarding_complete(request):
    """APP-29: presentation-only post-onboarding screen. Walks the admin
    through merge-PR -> configure-Pages -> set-CNAME. No API calls."""
    state = WizardState(request.session)
    derived = _derive_repo(state)
    if derived is None:
        return redirect("onboarding")
    org, repo = derived
    repo_url = f"https://github.com/{org}/{repo}"
    howto_url = (
        settings.POLICYCODEX_SOURCE_URL.rstrip("/")
        + "/blob/main/HOWTO-GitHub-Team-Setup.md"
    )
    return render(request, "onboarding/complete.html", {
        "repo_url": repo_url,
        "pages_url": f"{repo_url}/settings/pages",
        "cname_target": f"{org}.github.io",
        "howto_url": howto_url,
        "pr_url": request.session.pop("onboarding_pr_url", None),
    })
```

- [ ] **Step 5: Create the template**

Create `app/onboarding/templates/onboarding/complete.html`:

```html
{% extends "base.html" %}

{% block title %}Onboarding complete | PolicyCodex{% endblock %}

{% block content %}
  <div class="max-w-2xl mx-auto">
    <div class="card bg-base-100 border border-base-300">
      <div class="card-body space-y-6">
        <div>
          <h1 class="text-xl font-semibold text-base-content">Your handbook is almost live.</h1>
          <p class="text-sm text-slate-500 mt-1">
            Onboarding opened a pull request with your configuration. Three steps
            finish the job. Nothing publishes until you merge the pull request.
          </p>
        </div>

        <ol class="space-y-4">
          <li class="flex gap-3">
            <span class="badge badge-primary badge-sm mt-0.5">1</span>
            <div>
              <p class="font-medium text-base-content">Merge the onboarding pull request.</p>
              {% if pr_url %}
                <a href="{{ pr_url }}" class="link link-primary text-sm" target="_blank" rel="noopener">view PR &rarr;</a>
              {% else %}
                <p class="text-sm text-slate-500">Open your policy repository and merge the open onboarding pull request.</p>
              {% endif %}
            </div>
          </li>

          <li class="flex gap-3">
            <span class="badge badge-primary badge-sm mt-0.5">2</span>
            <div>
              <p class="font-medium text-base-content">Configure GitHub Pages.</p>
              <a href="{{ pages_url }}" class="link link-primary text-sm" target="_blank" rel="noopener">open settings &rarr;</a>
            </div>
          </li>

          <li class="flex gap-3">
            <span class="badge badge-primary badge-sm mt-0.5">3</span>
            <div>
              <p class="font-medium text-base-content">Set the CNAME record at your registrar.</p>
              <div class="flex items-center gap-2 mt-1">
                <code class="text-xs bg-base-200 rounded px-2 py-1">handbook &rarr; {{ cname_target }}</code>
                <button type="button" class="btn btn-ghost btn-xs" data-copy="{{ cname_target }}">Copy</button>
              </div>
            </div>
          </li>
        </ol>

        <div class="pt-4 border-t border-base-300">
          <a href="{% url 'catalog' %}" class="btn btn-primary btn-sm">Continue to your catalog</a>
        </div>

        <p class="text-xs text-slate-500">
          Full publishing sequence:
          <a href="{{ howto_url }}" class="link link-hover text-primary" target="_blank" rel="noopener">GitHub Team setup guide</a>.
        </p>
      </div>
    </div>
  </div>

  <script>
    document.querySelectorAll('[data-copy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        navigator.clipboard.writeText(btn.dataset.copy);
      });
    });
  </script>
{% endblock %}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_complete.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add app/onboarding/views.py app/onboarding/urls.py \
        app/onboarding/templates/onboarding/complete.html \
        app/onboarding/tests/test_onboarding_complete.py
git commit -m "feat(app-29): onboarding completion screen view + template"
```

---

## Task 2: Rewire both accept exits to the completion screen

**Files:**
- Modify: `app/onboarding/retention_policy.py`
- Modify: `app/onboarding/tests/test_onboarding_views.py`
- Modify: `app/onboarding/tests/test_screen7_htmx.py`

- [ ] **Step 1: Update the existing accept tests to expect the new redirect**

In `app/onboarding/tests/test_onboarding_views.py`, the three accept tests currently assert `/catalog/`. Change each to assert the completion-screen redirect.

`test_last_step_continue_completes_and_redirects_to_catalog` (rename to `..._redirects_to_complete`): change

```python
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"
```

to

```python
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == reverse("onboarding-complete")
    assert client.session["onboarding_pr_url"] == "https://github.com/acme/policies/pull/1"
```

`test_screen7_accept_scaffolds_bundle_and_finishes`: change its `assert resp.url == "/catalog/"` to `assert resp.url == reverse("onboarding-complete")`.

`test_screen7_accept_commits_config_and_opens_pr`: change its `assert resp.url == "/catalog/"` to `assert resp.url == reverse("onboarding-complete")`.

Ensure `from django.urls import reverse` is imported at the top of the file (add it if absent).

In `app/onboarding/tests/test_screen7_htmx.py`, update `test_accept_success_returns_204_and_hx_redirect_to_catalog` (rename to `..._to_complete`):

```python
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "accept"})
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == reverse("onboarding-complete")
    assert client.session["onboarding_pr_url"] == "https://github.com/acme/policies/pull/1"
```

(Leave the `back` and `save_exit` tests asserting `reverse("catalog")` unchanged — those navigation paths still go to the catalog.)

- [ ] **Step 2: Run the updated tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -k accept -v app/onboarding/tests/test_screen7_htmx.py -k "accept_success"`
Expected: FAIL — the handlers still redirect to `/catalog/` and never set `onboarding_pr_url`.

- [ ] **Step 3: Rewire the full-page accept exit**

In `app/onboarding/retention_policy.py`, the `handle()` accept branch currently ends (after a successful `finalize_onboarding`) with:

```python
        shutil.rmtree(staging.parent, ignore_errors=True)
        state.mark_complete(STEP_SLUG)
        messages.success(
            request,
            f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
        )
        return redirect("catalog")
```

Replace with:

```python
        shutil.rmtree(staging.parent, ignore_errors=True)
        state.mark_complete(STEP_SLUG)
        request.session["onboarding_pr_url"] = pr.get("url", "")
        return redirect("onboarding-complete")
```

- [ ] **Step 4: Rewire the HTMX accept exit**

In the same file, `_do_accept` currently ends with:

```python
    shutil.rmtree(staging.parent, ignore_errors=True)
    state.mark_complete(STEP_SLUG)
    messages.success(
        request,
        f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
    )
    return _hx_redirect(reverse("catalog"))
```

Replace with:

```python
    shutil.rmtree(staging.parent, ignore_errors=True)
    state.mark_complete(STEP_SLUG)
    request.session["onboarding_pr_url"] = pr.get("url", "")
    return _hx_redirect(reverse("onboarding-complete"))
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py app/onboarding/tests/test_screen7_htmx.py -v`
Expected: PASS (all accept tests now redirect to `onboarding-complete` and set the session key; `back`/`save_exit`/`finalize-failure`/guard tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add app/onboarding/retention_policy.py \
        app/onboarding/tests/test_onboarding_views.py \
        app/onboarding/tests/test_screen7_htmx.py
git commit -m "feat(app-29): route onboarding accept to the completion screen"
```

---

## Task 3: Full-suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS. Pre-APP-29 baseline was 513 passing + 5 corpus-gated skips (524 in AI-16's count; corpus tests skip in CI). APP-29 adds 6 new tests (Task 1) and renames/updates 4 existing ones (no net removals). Confirm zero failures and that the only skips are the corpus-gated ones.

- [ ] **Step 2: Confirm no stray `messages.success` onboarding-complete toast remains**

Run: `grep -rn "Onboarding complete. Configuration pull request" app/`
Expected: no matches (both toasts removed).

- [ ] **Step 3: Commit (only if Step 1/2 surfaced a fix)**

If the suite was already green and grep was clean, there is nothing to commit; skip. Otherwise:

```bash
git add -p
git commit -m "test(app-29): suite green after completion-screen rewire"
```

---

## Manual verification (post-merge, not a code step)

The DoD includes a browser pass, currently blocked on the Claude Chrome extension being disconnected (same blocker noted for APP-28b). When the extension reconnects, walk the wizard to completion at 1280x720 and confirm: the three-step checklist renders in the DaisyUI vocabulary, the Copy button writes `<org>.github.io` to the clipboard, the PR / settings / HOWTO links resolve, and "Continue to your catalog" lands on the catalog. If still blocked at ship time, say so explicitly rather than claiming the visual pass succeeded.

## Out of scope (do not implement)

- Any GitHub Pages API call, repo commit, or CNAME file commit (v0.2 P2.7).
- Polling or detecting PR-merge state.
- Collecting the handbook subdomain inside the wizard.
- A reusable app-wide copy-button component — there is no existing one; the small inline script in `complete.html` is sufficient for this single screen (YAGNI).
