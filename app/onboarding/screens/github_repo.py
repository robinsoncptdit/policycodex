"""DISC-07: Screen 4 github-repo. Connect or create; clone the working copy."""
from __future__ import annotations

import os
from pathlib import Path

from django.shortcuts import redirect, render

from app.onboarding import wizard
from app.onboarding.forms import GitHubRepoForm
from app.working_copy.config import WorkingCopyConfig
from app.working_copy.manager import WorkingCopyManager
from app.git_provider.github_provider import GitHubProvider

STEP_SLUG = "github-repo"


def _ctx(target, state, form=None, error=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "form": form or GitHubRepoForm(initial=state.get_data(STEP_SLUG)),
        "error": error,
    }


def _working_copy_root() -> Path:
    raw = os.environ.get("POLICYCODEX_WORKING_COPY_ROOT", "")
    if raw:
        return Path(os.path.expanduser(raw))
    return Path("/data/working-copy")


def _resolve_repo_url(cleaned: dict) -> str:
    """Return the clone URL, creating the repo first if mode == 'create'."""
    if cleaned["mode"] == "connect":
        return cleaned["repo_url"]
    result = GitHubProvider.create_repository(
        org=cleaned["org"], repo_name=cleaned["repo_name"], private=True,
    )
    return result["clone_url"]


def handle(request, target, state):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_exit":
            return redirect("catalog")
        if action == "back":
            prev = wizard.prev_step(STEP_SLUG)
            return redirect("onboarding_step", step=prev.slug)
        if action == "continue":
            form = GitHubRepoForm(request.POST)
            if not form.is_valid():
                return render(request, "onboarding/github_repo.html", _ctx(target, state, form))
            try:
                repo_url = _resolve_repo_url(form.cleaned_data)
            except Exception as exc:  # noqa: BLE001
                return render(request, "onboarding/github_repo.html",
                              _ctx(target, state, form, error=f"Could not provision repo: {exc}"))
            config = WorkingCopyConfig(
                repo_url=repo_url,
                branch=form.cleaned_data["branch"],
                root=_working_copy_root(),
            )
            try:
                WorkingCopyManager(config, GitHubProvider()).sync()
            except Exception as exc:  # noqa: BLE001
                return render(request, "onboarding/github_repo.html",
                              _ctx(target, state, form, error=f"Could not clone the repo: {exc}"))
            # Persist to the credential store so load_working_copy_config()
            # can find the repo URL on subsequent worker requests. Session
            # state alone won't reach the gating layer's _working_copy_dir().
            # Best-effort: skip if the store is unavailable (test contexts
            # without a /data/.credential-key mount); session state alone
            # still lets the user advance.
            try:
                from app.credentials import store
                store.set("policy_repo.url", repo_url)
                store.set("policy_repo.branch", form.cleaned_data["branch"])
            except RuntimeError:
                pass
            state.set_data(STEP_SLUG, {
                "mode": form.cleaned_data["mode"],
                "repo_url": repo_url,
                "branch": form.cleaned_data["branch"],
                "org": form.cleaned_data.get("org", ""),
                "repo_name": form.cleaned_data.get("repo_name", ""),
            })
            state.mark_complete(STEP_SLUG)
            nxt = wizard.next_step(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)

    return render(request, "onboarding/github_repo.html", _ctx(target, state))
