"""Onboarding wizard views (APP-08): routing, gating, and navigation shell."""
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from app.onboarding import forms as onboarding_forms
from app.onboarding import retention_policy
from app.onboarding import wizard
from app.onboarding.state import WizardState


def _nav_context(step, state):
    return {
        "step": step,
        "index": wizard.index_of(step.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(step.slug),
        "next_step": wizard.next_step(step.slug),
        "is_last": wizard.is_last(step.slug),
        "is_complete": state.is_complete(step.slug),
    }


def _step_context(target, state, form=None):
    ctx = _nav_context(target, state)
    if form is not None:
        ctx["form"] = form
    return ctx


@login_required
def onboarding_root(request):
    """Resume: send the admin to their current (furthest reached) step."""
    state = WizardState(request.session)
    return redirect("onboarding_step", step=state.current_step)


@login_required
def onboarding_step(request, step):
    target = wizard.get_step(step)
    if target is None:
        raise Http404(f"Unknown onboarding step: {step}")

    state = WizardState(request.session)

    if step == retention_policy.STEP_SLUG:
        return retention_policy.handle(request, target, state)

    if request.method == "POST":
        # Per-step form validation/processing lands in APP-09..16; the
        # skeleton treats every step's submit as a no-op save then navigates.
        action = request.POST.get("action")
        if action == "back":
            prev = wizard.prev_step(step)
            return redirect("onboarding_step", step=prev.slug if prev else step)
        if action == "save_exit":
            messages.info(request, "Your progress is saved. Resume onboarding any time.")
            return redirect("catalog")
        if action == "continue":
            form_cls = onboarding_forms.form_class_for(step)
            if form_cls is not None:
                form = form_cls(request.POST)
                if not form.is_valid():
                    # Invalid input: re-render with errors; do NOT advance.
                    return render(
                        request,
                        "onboarding/step.html",
                        _step_context(target, state, form),
                    )
                state.set_data(step, form.cleaned_data)
            state.mark_complete(step)
            if wizard.is_last(step):
                # APP-15/APP-16 hook: commit wizard config to the policy repo
                # and flip POLICYCODEX_ONBOARDING_COMPLETE. Not done here.
                messages.success(request, "Onboarding steps complete.")
                return redirect("catalog")
            nxt = wizard.next_step(step)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
        # Unknown or missing action: defensive re-render only. The normal
        # wizard UI never posts without a known action, so binding request.POST
        # here (which may show form errors) is acceptable for this dead path.
        form_cls = onboarding_forms.form_class_for(step)
        form = form_cls(request.POST) if form_cls is not None else None
        return render(request, "onboarding/step.html", _step_context(target, state, form))

    # GET gating: cannot skip ahead of the furthest step reached. Revisiting
    # the current step or any earlier/completed step is allowed. GET never
    # mutates current_step; only a `continue` POST advances it (keeps
    # furthest_step monotonic so backward review does not trap the user).
    furthest = state.furthest_step()
    if wizard.index_of(step) > wizard.index_of(furthest):
        return redirect("onboarding_step", step=furthest)

    form_cls = onboarding_forms.form_class_for(step)
    form = form_cls(initial=state.get_data(step)) if form_cls is not None else None
    return render(request, "onboarding/step.html", _step_context(target, state, form))


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
