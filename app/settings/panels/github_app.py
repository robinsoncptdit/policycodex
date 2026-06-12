"""GitHub App panel. Manual paste + Test Connection + Save + Revoke.

Manifest flow lands in a follow-up task; it will render above the manual
form, which collapses to a <details>. SHA-256 + canonicalization signature
pin: Test stores a signature in session, Save requires the signature to
match (forces user to Test before Save)."""
from __future__ import annotations

import hashlib

from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from app.credentials import store
from app.git_provider.github_provider import GitHubProvider
from app.settings.base import SettingsPanel, DangerAction, SetupAction
from app.settings.registry import register


_TEST_OK_SESSION_KEY = "github_app_test_ok_signature"


def _canonicalize(pem: str) -> bytes:
    return pem.replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8")


def _signature(app_id: str, installation_id: str, pem: str) -> str:
    return (
        f"{app_id.strip()}|"
        f"{installation_id.strip()}|"
        f"{hashlib.sha256(_canonicalize(pem)).hexdigest()[:16]}"
    )


class _Form(forms.Form):
    app_id = forms.CharField(max_length=32, label="App ID")
    installation_id = forms.CharField(max_length=32, label="Installation ID")
    private_key_pem = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "spellcheck": "false"}),
        label="Private key (PEM)",
    )


class GitHubAppPanel(SettingsPanel):
    slug = "github-app"
    title = "GitHub App"
    nav_group = "Credentials"

    def render(self, request, *, form=None, message=None, error=None):
        from app.settings.views import _nav_groups
        initial = {}
        for k, field in (
            ("github_app.app_id", "app_id"),
            ("github_app.installation_id", "installation_id"),
            ("github_app.private_key_pem", "private_key_pem"),
        ):
            if store.has(k):
                initial[field] = store.get(k)
        return render(request, "settings/panels/github_app.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(),
            "form": form or _Form(initial=initial),
            "panel_setup_actions": self.setup_actions(request),
            "panel_danger_actions": self.danger_actions(request),
            "message": message,
            "error": error,
        })

    def save(self, request):
        if request.POST.get("action") == "revoke":
            return self._revoke(request)
        form = _Form(request.POST)
        if not form.is_valid():
            return self.render(request, form=form)
        sig = _signature(
            form.cleaned_data["app_id"],
            form.cleaned_data["installation_id"],
            form.cleaned_data["private_key_pem"],
        )
        if request.session.get(_TEST_OK_SESSION_KEY) != sig:
            return self.render(request, form=form, error="Test the connection first.")
        store.set("github_app.app_id", form.cleaned_data["app_id"])
        store.set("github_app.installation_id", form.cleaned_data["installation_id"])
        store.set("github_app.private_key_pem", form.cleaned_data["private_key_pem"])
        return self.render(request, form=form, message="GitHub App credentials saved.")

    def _revoke(self, request):
        if request.POST.get("confirm_token") != "REVOKE":
            return self.render(request, error="Type REVOKE to confirm.")
        # The store has no per-key delete; overwrite with empty so a
        # subsequent has() still returns True but get() returns "".
        store.set("github_app.private_key_pem", "")
        request.session.pop(_TEST_OK_SESSION_KEY, None)
        return self.render(request, message="Private key revoked. Paste a fresh one to reconnect.")

    def test(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": "Fill in all three fields first."},
            }))
        try:
            GitHubProvider.test_credentials(
                app_id=form.cleaned_data["app_id"],
                installation_id=form.cleaned_data["installation_id"],
                private_key_pem=form.cleaned_data["private_key_pem"],
            )
        except Exception as exc:  # noqa: BLE001 surfaced to user
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": str(exc)},
            }))
        request.session[_TEST_OK_SESSION_KEY] = _signature(
            form.cleaned_data["app_id"],
            form.cleaned_data["installation_id"],
            form.cleaned_data["private_key_pem"],
        )
        return HttpResponse(render_to_string("settings/_test_result.html", {
            "result": {"state": "ok", "message": "Connected."},
        }))

    def setup_actions(self, request):
        actions = []
        if not store.has("github_app.app_id"):
            actions.append(SetupAction(
                label="Set up automatically (recommended)",
                description=(
                    "Three clicks. PolicyCodex creates the GitHub App on your account, "
                    "you confirm on GitHub, you install it on your organization, and "
                    "PolicyCodex stores the credentials automatically."
                ),
                cta_label="Create PolicyCodex GitHub App",
                cta_url="/settings/github-app/manifest/start/",
            ))
        return actions

    def danger_actions(self, request):
        if store.has("github_app.private_key_pem") and store.get("github_app.private_key_pem"):
            return [DangerAction(
                label="Revoke this private key",
                description="Removes the PEM from the credential store. You will need to paste a fresh one (or generate a new one on GitHub) to reconnect.",
                cta_label="Revoke",
                cta_url="",  # handled by inline form
                confirm_token="REVOKE",
            )]
        return []


register(GitHubAppPanel())
