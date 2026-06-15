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
    store.set("github_app.app_id", "4021727")
    store.set("github_app.private_key_pem", "-----BEGIN PRIVATE KEY-----\nXYZ\n-----END PRIVATE KEY-----")


def test_install_callback_stores_installation_id(client, admin):
    client.force_login(admin)
    with patch("app.settings.panels.github_app_manifest._list_installations") as li:
        li.return_value = [{"id": 999888, "account": {"login": "diocese"}}]
        response = client.get("/settings/github-app/install/callback/", follow=True)
    from app.credentials import store
    assert store.get("github_app.installation_id") == "999888"


def test_install_callback_no_installation_shows_retry(client, admin):
    client.force_login(admin)
    with patch("app.settings.panels.github_app_manifest._list_installations") as li:
        li.return_value = []
        response = client.get("/settings/github-app/install/callback/")
    assert b"Install" in response.content


def test_list_installations_delegates_to_pygithub_provider():
    """The manifest panel no longer hand-rolls a JWT; it delegates to the
    git_provider so all GitHub App auth lives in one PyGithub-backed place."""
    from app.settings.panels import github_app_manifest as m
    from app.credentials import store
    store.set("github_app.app_id", "777")
    store.set("github_app.private_key_pem", "-----BEGIN PRIVATE KEY-----\nX")
    with patch("app.git_provider.github_provider.list_app_installations") as lai:
        lai.return_value = [{"id": 42, "target_type": "Organization"}]
        result = m._list_installations()
    assert result == [{"id": 42, "target_type": "Organization"}]
    lai.assert_called_once_with("777", "-----BEGIN PRIVATE KEY-----\nX")
