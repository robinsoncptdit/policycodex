import pytest
from unittest.mock import patch
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


def test_install_url_does_not_reuse_csrf_state_token(client, admin):
    """The GitHub install link must not echo the already-validated-and-popped
    manifest CSRF state token. (Clarity/hardening nit, F13.)"""
    client.force_login(admin)
    session = client.session
    session["github_app_manifest_state"] = "the-real-csrf-state-token-123"
    session.save()
    with patch("app.settings.panels.github_app_manifest._exchange_code") as exchange:
        exchange.return_value = {
            "id": 4021727,
            "pem": "-----BEGIN PRIVATE KEY-----\nXYZ\n-----END PRIVATE KEY-----",
            "webhook_secret": "shhh",
            "slug": "policycodex-7",
        }
        response = client.get(
            "/settings/github-app/manifest/callback/"
            "?code=temp123&state=the-real-csrf-state-token-123"
        )
    assert response.status_code == 200
    body = response.content.decode()
    assert "the-real-csrf-state-token-123" not in body, (
        "install_url must not echo the popped manifest CSRF state token"
    )
    assert "github.com/apps/policycodex-7/installations/new?state=" in body
