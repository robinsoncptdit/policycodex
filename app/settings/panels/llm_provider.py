"""Same SHA-256+canonicalization signature pattern as the original DISC-06
provider; same provider radio + key + Test Key + Save flow."""
from __future__ import annotations

import hashlib

from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from app.credentials import store
from app.settings.base import SettingsPanel
from app.settings.registry import register
from ai.claude_provider import ClaudeProvider


_TEST_OK_SESSION_KEY = "llm_provider_test_ok_signature"

PROVIDER_CHOICES = [
    ("claude", "Anthropic Claude (recommended)"),
    ("openai", "OpenAI"),
    ("gemini", "Google Gemini"),
    ("azure-openai", "Azure OpenAI"),
    ("local-llama", "Local Llama (self-hosted)"),
]


class _Form(forms.Form):
    provider = forms.ChoiceField(choices=PROVIDER_CHOICES, initial="claude")
    api_key = forms.CharField(required=False, max_length=512)


def _signature(provider: str, api_key: str) -> str:
    p = provider.strip()
    k = api_key.strip().encode("utf-8")
    return f"{p}|{hashlib.sha256(k).hexdigest()[:16]}"


class LLMProviderPanel(SettingsPanel):
    slug = "llm-provider"
    title = "AI provider"
    nav_group = "Credentials"

    def render(self, request, *, form=None, error=None, success=None):
        from app.settings.views import _nav_groups
        ctx = {
            "active_slug": self.slug,
            "panel_title": self.title,
            "nav_groups": _nav_groups(),
            "form": form or _Form(initial={"provider": "claude"}),
            "error": error,
            "success": success,
        }
        return render(request, "settings/panels/llm_provider.html", ctx)

    def save(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return self.render(request, form=form)
        provider = form.cleaned_data["provider"]
        if provider == "local-llama":
            store.set("llm.provider", provider)
            return self.render(request, form=form, success="Saved.")
        api_key = form.cleaned_data["api_key"]
        if not api_key:
            return self.render(request, form=form, error="Paste your API key.")
        sig = _signature(provider, api_key)
        if request.session.get(_TEST_OK_SESSION_KEY) != sig:
            return self.render(request, form=form, error="Test the key first.")
        store.set("llm.provider", provider)
        store.set(f"llm.{provider}.api_key", api_key)
        return self.render(request, form=form, success="Saved.")

    def test(self, request):
        form = _Form(request.POST)
        if not form.is_valid():
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": "Invalid input."},
            }))
        provider = form.cleaned_data["provider"]
        api_key = form.cleaned_data["api_key"]
        if provider == "local-llama":
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "ok", "message": "Local Llama needs no test."},
            }))
        if provider != "claude":
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": f"Test for {provider} is v0.2."},
            }))
        if not api_key:
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": "Paste your API key first."},
            }))
        try:
            ClaudeProvider.test_key(api_key)
        except Exception as exc:  # noqa: BLE001 surfaced to user
            return HttpResponse(render_to_string("settings/_test_result.html", {
                "result": {"state": "error", "message": str(exc)},
            }))
        request.session[_TEST_OK_SESSION_KEY] = _signature(provider, api_key)
        return HttpResponse(render_to_string("settings/_test_result.html", {
            "result": {"state": "ok", "message": "Key works."},
        }))


register(LLMProviderPanel())
