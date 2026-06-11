"""DISC-04: Screen 1 — create the first Django admin and log them in."""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render

from app.onboarding import wizard

User = get_user_model()
STEP_SLUG = "admin-account"


class AdminAccountForm(forms.Form):
    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField(label="Email")
    password = forms.CharField(
        widget=forms.PasswordInput, min_length=8,
        label="Password",
        help_text="At least 8 characters.",
        error_messages={"min_length": "Use at least 8 characters."},
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput, label="Confirm password"
    )

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        pw2 = cleaned.get("password_confirm")
        if pw and pw2 and pw != pw2:
            self.add_error("password_confirm", "Passwords do not match.")
        return cleaned


def _ctx(target, state, form=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "form": form or AdminAccountForm(),
    }


def handle(request, target, state):
    if User.objects.filter(is_superuser=True).exists():
        # Admin already exists; this screen has done its job.
        if request.user.is_authenticated:
            nxt = wizard.next_step(STEP_SLUG)
            state.mark_complete(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)
        return redirect("login")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_exit":
            return redirect("catalog")
        if action == "continue":
            form = AdminAccountForm(request.POST)
            if not form.is_valid():
                return render(request, "onboarding/admin_account.html", _ctx(target, state, form))
            user = User.objects.create_superuser(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            login(request, user)
            state.mark_complete(STEP_SLUG)
            nxt = wizard.next_step(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)

    return render(request, "onboarding/admin_account.html", _ctx(target, state))
