"""Policy Repository panel — base path.

This task implements: manual paste, Test (git ls-remote via the GH App
installation token when available), Save (writes policy_repo.* to credential
store + runs WorkingCopyManager.sync), Disconnect (clears credentials +
removes working-copy dir; GitHub is untouched), Create new repository,
Initialize this repository."""
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


def _initialize_repo(repo_url: str, branch: str) -> None:
    """Clone the repo to a temp dir, push the PolicyCodex skeleton in one
    commit (.policycodex/config.yaml with schema_version: 1, the L2
    foundational guard from repo-template/, a placeholder policies/ dir
    with .gitkeep), and best-effort configure branch protection.

    Idempotent — if .policycodex/ already exists in the repo, returns without
    committing.
    """
    import tempfile
    config_yaml = "schema_version: 1\n"
    guard_workflow_src = Path("repo-template/.github/workflows/foundational-guard.yml")
    guard_script_src = Path("repo-template/.github/scripts/foundational_guard.py")
    handbook_workflow_src = Path("repo-template/.github/workflows/build-handbook.yml")

    files = [
        (".policycodex/config.yaml", config_yaml),
        ("policies/.gitkeep", ""),
    ]
    if guard_workflow_src.exists():
        files.append((".github/workflows/foundational-guard.yml", guard_workflow_src.read_text()))
    if guard_script_src.exists():
        files.append((".github/scripts/foundational_guard.py", guard_script_src.read_text()))
    if handbook_workflow_src.exists():
        files.append((".github/workflows/build-handbook.yml", handbook_workflow_src.read_text()))

    # Rewrite the clone/push URL with the installation token so the helper
    # works inside Docker, where no ambient git credential helper exists.
    auth_url = repo_url
    if repo_url.startswith("https://github.com/"):
        try:
            token = GitHubProvider()._installation_token()
            auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
        except Exception:
            pass  # Fall back to ambient credentials for non-Docker dev.

    def _run(cmd, **kwargs):
        kwargs.setdefault("check", True)
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)
        try:
            return subprocess.run(cmd, **kwargs)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(exc.stderr.strip() or str(exc)) from exc

    with tempfile.TemporaryDirectory() as tmp:
        _run(["git", "clone", "--depth", "1", auth_url, tmp], timeout=60)
        if (Path(tmp) / ".policycodex").exists():
            return  # Idempotent.
        for rel, content in files:
            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        _run(["git", "-C", tmp, "add", "."])
        # -c flags supply a git identity for Docker containers that have
        # no global git config.
        _run([
            "git",
            "-c", "user.name=PolicyCodex",
            "-c", "user.email=bot@policycodex",
            "-C", tmp, "commit", "-m",
            "Initialize PolicyCodex skeleton\n\nCo-Authored-By: PolicyCodex <bot@policycodex>",
        ])
        _run(["git", "-C", tmp, "push", "origin", branch], timeout=60)

    # Branch protection is best-effort — the helper may not be implemented yet.
    try:
        GitHubProvider().enable_branch_protection(repo_url, branch, require_pr_review=True)
    except Exception:
        pass


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

    def is_configured(self, request) -> bool:
        return store.has("policy_repo.url") and bool(store.get("policy_repo.url"))

    def render(self, request, *, form=None, message=None, error=None):
        from app.settings.views import _nav_groups
        initial = {}
        if store.has("policy_repo.url"):
            initial["repo_url"] = store.get("policy_repo.url")
        if store.has("policy_repo.branch"):
            initial["branch"] = store.get("policy_repo.branch")
        # Populate the dropdown only when the GH App is fully configured.
        repos = []
        if all(store.has(k) for k in (
            "github_app.app_id",
            "github_app.installation_id",
            "github_app.private_key_pem",
        )):
            try:
                repos = GitHubProvider().list_installation_repos()
            except Exception:
                repos = []
        return render(request, "settings/panels/policy_repo.html", {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(request),
            "form": form or _Form(initial=initial),
            "current_url": store.get("policy_repo.url") if store.has("policy_repo.url") else None,
            "panel_setup_actions": self.setup_actions(request),
            "repos": repos,
            "message": message,
            "error": error,
        })

    def save(self, request):
        action = request.POST.get("action")
        if action == "disconnect":
            return self._disconnect(request)
        if action == "create_new":
            return self._create_new(request)
        if action == "initialize":
            return self._initialize(request)
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

    def _create_new(self, request):
        org = request.POST.get("org", "").strip()
        repo_name = request.POST.get("repo_name", "").strip()
        if not org or not repo_name:
            return self.render(request, error="Both org and repo name are required.")
        try:
            result = GitHubProvider.create_repository(
                org=org, repo_name=repo_name, private=True,
            )
        except Exception as exc:  # noqa: BLE001
            return self.render(request, error=f"Could not create repo: {exc}")
        repo_url = result["clone_url"].removesuffix(".git")
        branch = result.get("default_branch", "main")
        store.set("policy_repo.url", repo_url)
        store.set("policy_repo.branch", branch)
        # auto_init=True is set internally, so the repo already has main with a
        # README; push the PolicyCodex skeleton on top.
        try:
            _initialize_repo(repo_url, branch)
        except Exception as exc:  # noqa: BLE001
            return self.render(request, error=f"Repo created but initialization failed: {exc}")
        return self.render(request, message=f"Created and initialized {org}/{repo_name}.")

    def _initialize(self, request):
        if not store.has("policy_repo.url"):
            return self.render(request, error="Save a repository URL first.")
        repo_url = store.get("policy_repo.url")
        branch = store.get("policy_repo.branch") if store.has("policy_repo.branch") else "main"
        try:
            _initialize_repo(repo_url, branch)
        except Exception as exc:  # noqa: BLE001
            return self.render(request, error=str(exc))
        return self.render(request, message="Repository initialized with PolicyCodex skeleton.")

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

    def setup_actions(self, request):
        from app.settings.base import SetupAction
        if not store.has("policy_repo.url"):
            return [SetupAction(
                label="Create a new repository",
                description="PolicyCodex will create a private repo in your GitHub org, initialized with a README and the PolicyCodex skeleton in one step.",
                cta_label="Create",
                cta_url="javascript:document.getElementById('create-new-form').classList.toggle('hidden')",
            )]
        return [SetupAction(
            label="Initialize this repository",
            description="Pushes .policycodex/config.yaml, the L2 foundational guard, and the handbook build workflow in one commit. Idempotent — safe to click on an already-initialized repo.",
            cta_label="Initialize",
            cta_url="javascript:document.getElementById('initialize-form').classList.toggle('hidden')",
        )]

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
