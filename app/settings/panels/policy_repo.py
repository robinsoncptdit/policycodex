"""Policy Repository panel — base path.

This task implements: manual paste, Test (git ls-remote via the GH App
installation token when available), Save (writes policy_repo.* to credential
store + runs WorkingCopyManager.sync), Disconnect (clears credentials +
removes working-copy dir; GitHub is untouched)."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from app.credentials import store
from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import WorkingCopyConfig
from app.working_copy.manager import WorkingCopyManager
from app.settings.base import SettingsPanel
from app.settings.registry import register


_TEST_OK_SESSION_KEY = "policy_repo_test_ok_signature"


def _signature(repo_url: str, branch: str) -> str:
    s = f"{repo_url.strip()}|{branch.strip()}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _working_copy_root() -> Path:
    # Mirror app.working_copy.config: prefer the env var, then /data/working-copy
    # in Docker, then ~/.policycodex/working-copies for dev outside Docker.
    raw = os.environ.get("POLICYCODEX_WORKING_COPY_ROOT", "")
    if raw:
        return Path(os.path.expanduser(raw))
    if Path("/data").exists():
        return Path("/data/working-copy")
    return Path.home() / ".policycodex" / "working-copies"


def _git_ls_remote(repo_url: str, branch: str, token: str | None) -> bool:
    """Run `git ls-remote` against the URL. Returns True if the branch ref
    is present. Authenticated with the App's installation token via
    https://x-access-token:<token>@github.com/... when provided."""
    url = repo_url
    if token and url.startswith("https://github.com/"):
        url = url.replace("https://", f"https://x-access-token:{token}@")
    result = subprocess.run(
        ["git", "ls-remote", "--heads", url, branch],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0 and f"refs/heads/{branch}" in result.stdout


class _Form(forms.Form):
    repo_url = forms.URLField(max_length=512, label="Repository URL")
    branch = forms.CharField(max_length=128, initial="main")


class PolicyRepoPanel(SettingsPanel):
    slug = "policy-repo"
    title = "Policy repository"
    nav_group = "Diocese"

    def render(self, request, *, form=None, message=None, error=None):
        from app.settings.views import _nav_groups
        initial = {}
        if store.has("policy_repo.url"):
            initial["repo_url"] = store.get("policy_repo.url")
        if store.has("policy_repo.branch"):
            initial["branch"] = store.get("policy_repo.branch")
        return render(request, "settings/panels/policy_repo.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(),
            "form": form or _Form(initial=initial),
            "current_url": store.get("policy_repo.url") if store.has("policy_repo.url") else None,
            "message": message,
            "error": error,
        })

    def save(self, request):
        if request.POST.get("action") == "disconnect":
            return self._disconnect(request)
        return self._save_connect(request)

    def _save_connect(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return self.render(request, form=form)
        repo_url = form.cleaned_data["repo_url"]
        branch = form.cleaned_data["branch"]
        sig = _signature(repo_url, branch)
        if request.session.get(_TEST_OK_SESSION_KEY) != sig:
            return self.render(request, form=form, error="Test the repository first.")
        # Sync first; only write to the store on success. A failed sync that
        # already mutated the store leaves the user with current_url set to
        # an unfetched repo, which is worse than no save at all.
        try:
            config = WorkingCopyConfig(repo_url=repo_url, branch=branch, root=_working_copy_root())
            WorkingCopyManager(config, GitHubProvider()).sync()
        except Exception as exc:  # noqa: BLE001 surfaced to user
            return self.render(request, form=form, error=f"Sync failed: {exc}")
        store.set("policy_repo.url", repo_url)
        store.set("policy_repo.branch", branch)
        return self.render(request, form=form, message="Saved and synced.")

    def _disconnect(self, request):
        if request.POST.get("confirm_token") != "DISCONNECT":
            return self.render(request, error="Type DISCONNECT to confirm.")
        # The store has no per-key delete, so this wipes the whole credential
        # file — GitHub App and LLM credentials go with it. Re-enter via their
        # panels. The template warns the user before they confirm.
        cred_path = Path(os.environ.get("POLICYCODEX_CREDENTIAL_STORE_FILE", "/data/.credentials"))
        if cred_path.exists():
            cred_path.unlink()
        store._reset_cache()
        # Remove the local working copy.
        root = _working_copy_root()
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        return self.render(request, message="Disconnected from the policy repository.")

    def test(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": "Provide a repository URL and branch."},
            }))
        repo_url = form.cleaned_data["repo_url"]
        branch = form.cleaned_data["branch"]
        token = None
        try:
            token = GitHubProvider()._installation_token()
        except Exception:
            pass  # No GH App configured; ls-remote unauth for public repos.
        try:
            ok = _git_ls_remote(repo_url, branch, token)
        except Exception as exc:  # noqa: BLE001 surfaced to user
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": str(exc)},
            }))
        if ok:
            request.session[_TEST_OK_SESSION_KEY] = _signature(repo_url, branch)
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "ok", "message": f"Branch {branch} found."},
            }))
        return HttpResponse(render_to_string("settings/_test_result.html", {
            "result": {"state": "error", "message": f"Branch {branch} not found on the remote."},
        }))


register(PolicyRepoPanel())
