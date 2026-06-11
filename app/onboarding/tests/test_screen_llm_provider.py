"""DISC-06: Screen 3 llm-provider + API key + Test Key."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    u = User.objects.create_superuser("admin", "a@b.com", "pw")
    c = Client()
    c.login(username="admin", password="pw")
    # Pre-seed wizard state: admin-account + github-app complete, current=llm-provider.
    # Without this, gating Signal 3 bounces back to the furthest completed step.
    from app.onboarding.state import SESSION_KEY
    session = c.session
    session[SESSION_KEY] = {
        "current_step": "llm-provider",
        "completed": ["admin-account", "github-app"],
        "data": {},
    }
    session.save()
    return c


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from app.credentials import store
    key = tmp_path / ".credential-key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


def test_get_renders_with_anthropic_default(logged_in_admin):
    r = logged_in_admin.get("/onboarding/llm-provider/")
    assert r.status_code == 200
    assert b"Anthropic" in r.content
    assert b"Local Llama" in r.content


def test_local_llama_skips_test_and_continues(logged_in_admin):
    from app.credentials import store
    r = logged_in_admin.post("/onboarding/llm-provider/", {
        "action": "continue",
        "provider": "local-llama",
    })
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/github-repo/")
    assert store.get("llm.provider") == "local-llama"


def test_anthropic_test_key_success(logged_in_admin):
    with patch("ai.claude_provider.ClaudeProvider.test_key", return_value=True):
        r = logged_in_admin.post("/htmx/onboarding/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-test-1234",
        })
    assert r.status_code == 200
    assert b"data-state=\"ok\"" in r.content


def test_anthropic_test_key_failure(logged_in_admin):
    with patch("ai.claude_provider.ClaudeProvider.test_key", side_effect=RuntimeError("401 invalid_api_key")):
        r = logged_in_admin.post("/htmx/onboarding/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-bad",
        })
    assert r.status_code == 200
    assert b"data-state=\"error\"" in r.content
    assert b"401" in r.content


def test_anthropic_continue_without_test_blocks(logged_in_admin):
    r = logged_in_admin.post("/onboarding/llm-provider/", {
        "action": "continue",
        "provider": "claude",
        "api_key": "sk-ant-1234",
    })
    assert r.status_code == 200
    assert b"Test the key first" in r.content


def test_anthropic_continue_after_test_persists_key(logged_in_admin):
    from app.credentials import store
    with patch("ai.claude_provider.ClaudeProvider.test_key", return_value=True):
        logged_in_admin.post("/htmx/onboarding/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-good-1234",
        })
        r = logged_in_admin.post("/onboarding/llm-provider/", {
            "action": "continue",
            "provider": "claude",
            "api_key": "sk-ant-good-1234",
        })
    assert r.status_code == 302
    assert store.get("llm.provider") == "claude"
    assert store.get("llm.claude.api_key") == "sk-ant-good-1234"
