"""DISC-05: Screen 2 github-app credentials.

Two endpoints:
  GET  /onboarding/github-app/                         -> render form
  POST /onboarding/github-app/                         -> continue (blocks unless test passed)
  POST /htmx/onboarding/github-app/test/               -> Test Connection (HTMX fragment)
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from app.credentials import store
from app.git_provider.github_provider import GitHubProvider
from app.onboarding import wizard

STEP_SLUG = "github-app"
_TEST_OK_SESSION_KEY = "github_app_test_ok_signature"


class GitHubAppForm(forms.Form):
    app_id = forms.CharField(max_length=32, label="App ID")
    installation_id = forms.CharField(max_length=32, label="Installation ID")
    private_key_pem = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "spellcheck": "false"}),
        label="Private key (PEM)",
    )


def _signature(data: dict) -> str:
    return f"{data.get('app_id', '')}|{data.get('installation_id', '')}|{hash(data.get('private_key_pem', ''))}"


def _ctx(target, state, form=None, error=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "form": form or GitHubAppForm(),
        "error": error,
    }


def handle(request, target, state):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_exit":
            return redirect("catalog")
        if action == "back":
            return redirect("onboarding_step", step=wizard.prev_step(STEP_SLUG).slug)
        if action == "continue":
            form = GitHubAppForm(request.POST)
            if not form.is_valid():
                return render(request, "onboarding/github_app.html", _ctx(target, state, form))
            sig = _signature(form.cleaned_data)
            if request.session.get(_TEST_OK_SESSION_KEY) != sig:
                return render(request, "onboarding/github_app.html",
                              _ctx(target, state, form, error="Test the connection first."))
            store.set("github_app.app_id", form.cleaned_data["app_id"])
            store.set("github_app.installation_id", form.cleaned_data["installation_id"])
            store.set("github_app.private_key_pem", form.cleaned_data["private_key_pem"])
            state.mark_complete(STEP_SLUG)
            nxt = wizard.next_step(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)

    return render(request, "onboarding/github_app.html", _ctx(target, state))


@login_required
@require_POST
def test_connection(request):
    """HTMX endpoint: tries the credentials, returns a fragment with state=ok|error."""
    form = GitHubAppForm(request.POST)
    if not form.is_valid():
        html = render_to_string("onboarding/_github_app_test.html", {
            "state": "error",
            "message": "Fill in all three fields first.",
        })
        return HttpResponse(html)
    try:
        GitHubProvider.test_credentials(
            app_id=form.cleaned_data["app_id"],
            installation_id=form.cleaned_data["installation_id"],
            private_key_pem=form.cleaned_data["private_key_pem"],
        )
    except Exception as exc:  # noqa: BLE001 surfaced to user
        html = render_to_string("onboarding/_github_app_test.html", {
            "state": "error",
            "message": str(exc),
        })
        return HttpResponse(html)
    request.session[_TEST_OK_SESSION_KEY] = _signature(form.cleaned_data)
    html = render_to_string("onboarding/_github_app_test.html", {
        "state": "ok",
        "message": "Connected.",
    })
    return HttpResponse(html)
