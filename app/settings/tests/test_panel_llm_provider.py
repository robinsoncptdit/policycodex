import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    # Seeded admin already exists; reuse it.
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


def test_get_renders_with_anthropic_default(client, admin):
    client.force_login(admin)
    response = client.get("/settings/llm-provider/")
    assert response.status_code == 200
    assert b"Anthropic" in response.content
    assert b"Local Llama" in response.content


def test_test_key_success_returns_ok(client, admin):
    client.force_login(admin)
    with patch("ai.claude_provider.ClaudeProvider.test_key", return_value=True):
        response = client.post("/htmx/settings/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-good",
        })
    assert response.status_code == 200
    assert b'data-state="ok"' in response.content


def test_test_key_failure_returns_error(client, admin):
    client.force_login(admin)
    with patch("ai.claude_provider.ClaudeProvider.test_key",
               side_effect=RuntimeError("401 invalid_api_key")):
        response = client.post("/htmx/settings/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-bad",
        })
    assert response.status_code == 200
    assert b'data-state="error"' in response.content
    assert b"401" in response.content


def test_local_llama_skips_test_on_save(client, admin):
    client.force_login(admin)
    from app.credentials import store
    response = client.post("/settings/llm-provider/", {
        "provider": "local-llama",
    })
    assert store.get("llm.provider") == "local-llama"


def test_save_anthropic_without_test_pin_blocks(client, admin):
    client.force_login(admin)
    response = client.post("/settings/llm-provider/", {
        "provider": "claude",
        "api_key": "sk-ant-untested",
    })
    assert response.status_code == 200
    assert b"Test the key" in response.content


def test_save_after_test_pin_persists(client, admin):
    client.force_login(admin)
    from app.credentials import store
    with patch("ai.claude_provider.ClaudeProvider.test_key", return_value=True):
        client.post("/htmx/settings/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-good",
        })
        response = client.post("/settings/llm-provider/", {
            "provider": "claude",
            "api_key": "sk-ant-good",
        })
    assert store.get("llm.provider") == "claude"
    assert store.get("llm.claude.api_key") == "sk-ant-good"


def test_success_chip_renders_above_intro_paragraph(client, admin):
    """Success alert should land above the panel's intro paragraph,
    not buried between the intro and the form."""
    from app.credentials import store
    from unittest.mock import patch
    client.force_login(admin)
    with patch("ai.claude_provider.ClaudeProvider.test_key", return_value=True):
        # Test then save to land in the success state.
        client.post("/htmx/settings/llm-provider/test/", {
            "provider": "claude",
            "api_key": "sk-ant-good",
        })
        response = client.post("/settings/llm-provider/", {
            "provider": "claude",
            "api_key": "sk-ant-good",
        })
    body = response.content.decode()
    saved_idx = body.find("Saved.")
    intro_idx = body.find("PolicyCodex needs an LLM")
    assert saved_idx >= 0 and intro_idx >= 0
    assert saved_idx < intro_idx, (
        f"Success chip at {saved_idx} should appear before intro at {intro_idx}"
    )
