import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
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


def test_manifest_start_renders_auto_submit_form(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/manifest/start/")
    assert response.status_code == 200
    assert b"github.com/settings/apps/new" in response.content
    assert b"manifest" in response.content


def test_manifest_callback_invalid_state_rejected(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/manifest/callback/?code=abc&state=tampered")
    assert response.status_code == 200
    assert b"state validation failed" in response.content.lower()


def test_manifest_callback_success_stores_credentials(client, admin):
    client.force_login(admin)
    session = client.session
    session["github_app_manifest_state"] = "valid-state-xyz"
    session.save()
    with patch("app.settings.panels.github_app_manifest._exchange_code") as exchange:
        exchange.return_value = {
            "id": 4021727,
            "pem": "-----BEGIN PRIVATE KEY-----\nXYZ\n-----END PRIVATE KEY-----",
            "webhook_secret": "shhh",
        }
        response = client.get(
            "/settings/github-app/manifest/callback/?code=temp123&state=valid-state-xyz",
            follow=True,
        )
    from app.credentials import store
    assert store.get("github_app.app_id") == "4021727"
    assert "BEGIN PRIVATE KEY" in store.get("github_app.private_key_pem")


def test_manifest_callback_conversion_failure_offers_retry(client, admin):
    client.force_login(admin)
    session = client.session
    session["github_app_manifest_state"] = "valid-state-xyz"
    session.save()
    with patch("app.settings.panels.github_app_manifest._exchange_code",
               side_effect=RuntimeError("network timeout")):
        response = client.get(
            "/settings/github-app/manifest/callback/?code=temp123&state=valid-state-xyz"
        )
    assert b"Retry" in response.content
    assert b"network timeout" in response.content


def test_setup_action_shows_when_no_app_configured(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    assert b"Create PolicyCodex GitHub App" in response.content


def test_setup_action_hidden_when_app_already_configured(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    response = client.get("/settings/github-app/")
    assert b"Create PolicyCodex GitHub App" not in response.content
