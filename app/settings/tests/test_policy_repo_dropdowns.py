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


def test_dropdowns_populated_when_app_installed(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    with patch("app.settings.panels.policy_repo.GitHubProvider") as gp_cls:
        gp = gp_cls.return_value
        gp.list_installation_repos.return_value = [
            {"full_name": "diocese/policies", "default_branch": "main"},
            {"full_name": "diocese/intranet", "default_branch": "main"},
        ]
        response = client.get("/settings/policy-repo/")
    assert b"diocese/policies" in response.content
    assert b"diocese/intranet" in response.content


def test_dropdowns_silent_when_app_not_installed(client, admin):
    client.force_login(admin)
    # No GH App in store. Page still renders.
    response = client.get("/settings/policy-repo/")
    assert response.status_code == 200
