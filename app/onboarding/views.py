"""Onboarding wizard views (APP-08 / DISC-03): routing, gating, and per-screen dispatch."""
from pathlib import Path
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

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


def _admin_exists() -> bool:
    User = get_user_model()
    return User.objects.filter(is_superuser=True).exists()


def _working_copy_dir() -> Path:
    """Return the local clone path; tests patch this."""
    from app.working_copy.config import load_working_copy_config
    try:
        return load_working_copy_config().working_dir
    except RuntimeError:
        return Path("/data/working-copy/__absent__")


def _gate_for(step: str, request, state) -> object | None:
    """Run gating signals in order; return a redirect Response if blocked, else None."""
    # Signal 1: admin presence. Pre-bootstrap, admin-account is reachable
    # unauthenticated so the first user can create themselves.
    if not _admin_exists():
        if step != "admin-account":
            return redirect("onboarding_step", step="admin-account")
        return None
    # Signal 1b: once an admin exists, all wizard screens require login.
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    # Signal 2: working-copy presence (only required for screen 6 onward).
    requires_working_copy = step in ("retention-policy", "policy-documents")
    if requires_working_copy and not _working_copy_dir().exists():
        return redirect("onboarding_step", step="github-repo")
    # Signal 3: cannot jump past furthest_step.
    furthest = state.furthest_step()
    if wizard.index_of(step) > wizard.index_of(furthest):
        return redirect("onboarding_step", step=furthest)
    return None


def _resume_target(state) -> str:
    """Resolve which onboarding URL to send the user to."""
    # DISC-11 will surface in-progress runs; for now no inventory model exists.
    try:
        from app.inventory.models import InventoryRun
        if InventoryRun.objects.filter(status="running").exists():
            return reverse("inventory")
    except Exception:
        pass
    return reverse("onboarding_step", kwargs={"step": state.current_step})


def _onboarding_root_unauthenticated(request):
    """Handle unauthenticated access to /onboarding/ — route to screen 1 if no
    admin exists, otherwise redirect to login."""
    if not _admin_exists():
        return redirect("onboarding_step", step="admin-account")
    return redirect(f"/login/?next={request.path}")


def onboarding_root(request):
    """Resume: send the admin to the right place based on gating signals."""
    if not request.user.is_authenticated:
        return _onboarding_root_unauthenticated(request)
    state = WizardState(request.session)
    return redirect(_resume_target(state))


def _generic_step(request, target, state):
    """Generic form-driven step (used by github-repo until DISC-07 lifts it)."""
    step = target.slug
    if request.method == "POST":
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
                    return render(request, "onboarding/step.html", _step_context(target, state, form))
                state.set_data(step, form.cleaned_data)
            state.mark_complete(step)
            nxt = wizard.next_step(step)
            if nxt is None:
                return redirect("inventory")
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
        # Unknown or missing action: defensive re-render.
        form_cls = onboarding_forms.form_class_for(step)
        form = form_cls(request.POST) if form_cls is not None else None
        return render(request, "onboarding/step.html", _step_context(target, state, form))

    form_cls = onboarding_forms.form_class_for(step)
    form = form_cls(initial=state.get_data(step)) if form_cls is not None else None
    return render(request, "onboarding/step.html", _step_context(target, state, form))


def onboarding_step(request, step):
    target = wizard.get_step(step)
    if target is None:
        raise Http404(f"Unknown onboarding step: {step}")

    state = WizardState(request.session)
    gated = _gate_for(step, request, state)
    if gated is not None:
        return gated

    # Per-screen handlers (DISC-04..DISC-10). Dispatched by slug.
    # Each try/ImportError block is scaffold debt: remove when the DISC ticket lands.

    if step == "admin-account":
        from app.onboarding.screens import admin_account
        return admin_account.handle(request, target, state)

    if step == "github-app":
        from app.onboarding.screens import github_app
        return github_app.handle(request, target, state)

    if step == "llm-provider":
        # DISC-06 scaffold; remove when screen lands
        try:
            from app.onboarding.screens import llm_provider
            return llm_provider.handle(request, target, state)
        except ImportError:
            return _generic_step(request, target, state)

    if step == "configuration":
        # DISC-08 scaffold; remove when screen lands
        try:
            from app.onboarding.screens import configuration
            return configuration.handle(request, target, state)
        except ImportError:
            return _generic_step(request, target, state)

    if step == "policy-documents":
        # DISC-10 scaffold; remove when screen lands
        try:
            from app.onboarding.screens import policy_documents
            return policy_documents.handle(request, target, state)
        except ImportError:
            return _generic_step(request, target, state)

    if step == "retention-policy":
        return retention_policy.handle(request, target, state)

    # github-repo keeps today's generic-form path until DISC-07 lifts it.
    return _generic_step(request, target, state)


def _derive_repo(state):
    """Return (org, repo) from the github-repo wizard data, or None.

    connect mode parses the repo_url; create mode reads org + repo_name.
    Returns None when the data is missing or org/repo cannot be derived.
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
