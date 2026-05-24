"""Onboarding wizard views (APP-08): routing, gating, and navigation shell."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from app.onboarding import forms as onboarding_forms
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
        # Unknown or missing action: fall through to a defensive re-render.
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
