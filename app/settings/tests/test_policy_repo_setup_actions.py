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


def test_create_new_calls_github_app(client, admin):
    client.force_login(admin)
    with patch("app.settings.panels.policy_repo.GitHubProvider") as gp_cls, \
         patch("app.settings.panels.policy_repo._initialize_repo"):
        gp_cls.create_repository.return_value = {
            "clone_url": "https://github.com/diocese/new.git",
            "html_url": "https://github.com/diocese/new",
            "full_name": "diocese/new",
        }
        response = client.post("/settings/policy-repo/", {
            "action": "create_new",
            "org": "diocese",
            "repo_name": "new-policies",
        })
    gp_cls.create_repository.assert_called_once_with(
        org="diocese", repo_name="new-policies", private=True,
    )
    from app.credentials import store
    # repo_url has .git stripped via removesuffix.
    assert store.get("policy_repo.url") == "https://github.com/diocese/new"


def test_initialize_repo_pushes_skeleton(client, admin, tmp_path):
    client.force_login(admin)
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/diocese/policies")
    store.set("policy_repo.branch", "main")
    with patch("app.settings.panels.policy_repo._initialize_repo") as init:
        response = client.post("/settings/policy-repo/", {"action": "initialize"})
    init.assert_called_once()
