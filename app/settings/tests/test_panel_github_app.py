import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()
_PEM = "-----BEGIN PRIVATE KEY-----\nXYZ\n-----END PRIVATE KEY-----"


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


def test_get_renders_form(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    assert response.status_code == 200
    assert b"App ID" in response.content


def test_test_connection_success(client, admin):
    client.force_login(admin)
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials",
               return_value=True):
        response = client.post("/htmx/settings/github-app/test/", {
            "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
        })
    assert b'data-state="ok"' in response.content


def test_save_without_pinning_blocks(client, admin):
    client.force_login(admin)
    response = client.post("/settings/github-app/", {
        "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
    })
    assert b"Click Test connection" in response.content


def test_save_after_pinning_persists(client, admin):
    client.force_login(admin)
    from app.credentials import store
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials",
               return_value=True):
        client.post("/htmx/settings/github-app/test/", {
            "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
        })
        client.post("/settings/github-app/", {
            "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
        })
    assert store.get("github_app.app_id") == "1"
    assert store.get("github_app.installation_id") == "2"
    assert store.get("github_app.private_key_pem") == _PEM


def test_revoke_clears_pem(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", _PEM)
    response = client.post("/settings/github-app/", {
        "action": "revoke",
        "confirm_token": "REVOKE",
    })
    # PEM is cleared by overwriting with empty (store has no delete).
    assert store.get("github_app.private_key_pem") == ""


_PEM2 = "-----BEGIN PRIVATE KEY-----\nDIFFERENT\n-----END PRIVATE KEY-----"


def test_save_with_no_test_pin_shows_test_first_message(client, admin):
    client.force_login(admin)
    response = client.post("/settings/github-app/", {
        "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
    })
    assert b"Click Test connection" in response.content


def test_save_with_stale_test_pin_shows_credentials_changed(client, admin):
    from unittest.mock import patch
    client.force_login(admin)
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials",
               return_value=True):
        # Test PEM A.
        client.post("/htmx/settings/github-app/test/", {
            "app_id": "1", "installation_id": "2", "private_key_pem": _PEM,
        })
        # Save with PEM B.
        response = client.post("/settings/github-app/", {
            "app_id": "1", "installation_id": "2", "private_key_pem": _PEM2,
        })
    body = response.content.lower()
    assert b"credentials changed" in body or b"test again" in body


def test_intro_does_not_contradict_setup_action(client, admin):
    """The setup-action card says 'three clicks' — the intro must not
    tell the user to paste credentials when no credentials are saved."""
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    body = response.content.decode()
    # When no App is configured (no credentials in store), the
    # recommended path is the manifest flow. The intro should not
    # contradict that by telling the user to paste.
    assert "Paste your App ID" not in body
    assert "Paste your" not in body or "Paste a new" in body
