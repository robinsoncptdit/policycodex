"""Onboarding wizard views (APP-08): routing, gating, and navigation shell."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

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

    # GET gating: cannot skip ahead of the furthest step reached. Revisiting
    # the current step or any earlier/completed step is allowed. GET never
    # mutates current_step; only a `continue` POST advances it (keeps
    # furthest_step monotonic so backward review does not trap the user).
    furthest = state.furthest_step()
    if wizard.index_of(step) > wizard.index_of(furthest):
        return redirect("onboarding_step", step=furthest)

    return render(request, "onboarding/step.html", _nav_context(target, state))
