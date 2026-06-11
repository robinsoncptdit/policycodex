"""DISC-08: Screen 5 configuration. One screen, four sections with LA defaults."""
from __future__ import annotations

from django import forms
from django.shortcuts import redirect, render

from app.onboarding import wizard

STEP_SLUG = "configuration"

ADDRESS_SCHEMES = [
    ("chapter-section-item", "Chapter-Section-Item (LA default)"),
    ("department-code", "Department code (Catholic healthcare)"),
]
VERSIONING = [
    ("semver", "Semantic versioning (1.0, 1.1, 2.0) - recommended"),
]


class ConfigurationForm(forms.Form):
    address_scheme = forms.ChoiceField(choices=ADDRESS_SCHEMES, initial="chapter-section-item")
    versioning = forms.ChoiceField(choices=VERSIONING, initial="semver")
    reviewer_roles = forms.CharField(
        initial="CFO,HR Director,General Counsel",
        help_text="Comma-separated list of reviewer titles.",
    )
    retention_admin_years = forms.IntegerField(initial=7, min_value=1, max_value=99)
    retention_operational_years = forms.IntegerField(initial=3, min_value=1, max_value=99)

    def clean_reviewer_roles(self):
        raw = self.cleaned_data["reviewer_roles"]
        return [s.strip() for s in raw.split(",") if s.strip()]


def _ctx(target, state, form=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "form": form or ConfigurationForm(initial=state.get_data(STEP_SLUG) or None),
    }


def handle(request, target, state):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_exit":
            return redirect("catalog")
        if action == "back":
            return redirect("onboarding_step", step=wizard.prev_step(STEP_SLUG).slug)
        if action == "continue":
            form = ConfigurationForm(request.POST)
            if not form.is_valid():
                return render(request, "onboarding/configuration.html", _ctx(target, state, form))
            # reviewer_roles is cleaned to list[str] — JSON-serializable for session storage.
            state.set_data(STEP_SLUG, form.cleaned_data)
            state.mark_complete(STEP_SLUG)
            nxt = wizard.next_step(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
    return render(request, "onboarding/configuration.html", _ctx(target, state))
