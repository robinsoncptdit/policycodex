"""DISC-06: Screen 3 llm-provider + API key + Test Key.

Two endpoints:
  GET  /onboarding/llm-provider/               -> render form
  POST /onboarding/llm-provider/               -> continue (blocks unless test passed for keyed providers)
  POST /htmx/onboarding/llm-provider/test/     -> Test Key (HTMX fragment)
"""
from __future__ import annotations

import hashlib

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from app.credentials import store
from ai.claude_provider import ClaudeProvider
from app.onboarding import wizard

STEP_SLUG = "llm-provider"
_TEST_OK_SESSION_KEY = "llm_provider_test_ok_signature"

PROVIDER_CHOICES = [
    ("claude", "Anthropic Claude (recommended)"),
    ("openai", "OpenAI"),
    ("gemini", "Google Gemini"),
    ("azure-openai", "Azure OpenAI"),
    ("local-llama", "Local Llama (self-hosted)"),
]


class LLMProviderForm(forms.Form):
    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES, widget=forms.RadioSelect, initial="claude",
        label="AI provider",
    )
    api_key = forms.CharField(required=False, max_length=512, label="API key")


def _signature(data: dict) -> str:
    # SHA-256 not Python's hash(): the latter is per-process randomized via
    # PYTHONHASHSEED, so multi-worker gunicorn fingerprints the same API key
    # differently on each worker and Continue rejects a just-tested form.
    key = data.get("api_key", "").encode("utf-8")
    return f"{data.get('provider', '')}|{hashlib.sha256(key).hexdigest()[:16]}"


def _ctx(target, state, form=None, error=None):
    return {
        "step": target,
        "index": wizard.index_of(target.slug) + 1,
        "total": len(wizard.STEPS),
        "prev_step": wizard.prev_step(target.slug),
        "next_step": wizard.next_step(target.slug),
        "is_last": wizard.is_last(target.slug),
        "is_complete": state.is_complete(target.slug),
        "form": form or LLMProviderForm(),
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
            form = LLMProviderForm(request.POST)
            if not form.is_valid():
                return render(request, "onboarding/llm_provider.html", _ctx(target, state, form))
            provider = form.cleaned_data["provider"]
            if provider == "local-llama":
                store.set("llm.provider", provider)
            else:
                api_key = form.cleaned_data["api_key"]
                if not api_key:
                    return render(request, "onboarding/llm_provider.html",
                                  _ctx(target, state, form, error="Paste your API key."))
                sig = _signature({"provider": provider, "api_key": api_key})
                if request.session.get(_TEST_OK_SESSION_KEY) != sig:
                    return render(request, "onboarding/llm_provider.html",
                                  _ctx(target, state, form, error="Test the key first."))
                store.set("llm.provider", provider)
                store.set(f"llm.{provider}.api_key", api_key)
            state.mark_complete(STEP_SLUG)
            nxt = wizard.next_step(STEP_SLUG)
            state.set_current(nxt.slug)
            return redirect("onboarding_step", step=nxt.slug)

    return render(request, "onboarding/llm_provider.html", _ctx(target, state))


@login_required
@require_POST
def test_key(request):
    """HTMX endpoint: tries the API key, returns a fragment with data-state=ok|error."""
    provider = request.POST.get("provider", "")
    api_key = request.POST.get("api_key", "")
    if provider == "local-llama":
        return HttpResponse(render_to_string("onboarding/_llm_provider_test.html", {
            "state": "ok",
            "message": "Local Llama needs no test.",
        }))
    if provider != "claude":
        return HttpResponse(render_to_string("onboarding/_llm_provider_test.html", {
            "state": "error",
            "message": f"Test for {provider} not implemented yet — v0.2.",
        }))
    if not api_key:
        return HttpResponse(render_to_string("onboarding/_llm_provider_test.html", {
            "state": "error",
            "message": "Paste your API key first.",
        }))
    try:
        ClaudeProvider.test_key(api_key)
    except Exception as exc:  # noqa: BLE001 surfaced to user
        return HttpResponse(render_to_string("onboarding/_llm_provider_test.html", {
            "state": "error",
            "message": str(exc),
        }))
    request.session[_TEST_OK_SESSION_KEY] = _signature({"provider": provider, "api_key": api_key})
    return HttpResponse(render_to_string("onboarding/_llm_provider_test.html", {
        "state": "ok",
        "message": "Key works.",
    }))
