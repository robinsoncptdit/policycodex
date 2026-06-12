import pytest
from pathlib import Path
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


def test_get_renders_form(client, admin):
    client.force_login(admin)
    response = client.get("/settings/policy-repo/")
    assert response.status_code == 200
    assert b"Repository URL" in response.content


def test_test_endpoint_ok(client, admin):
    client.force_login(admin)
    with patch("app.settings.panels.policy_repo._git_ls_remote", return_value=True):
        response = client.post("/htmx/settings/policy-repo/test/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
    assert b'data-state="ok"' in response.content


def test_save_writes_to_store_and_syncs(client, admin):
    client.force_login(admin)
    from app.credentials import store
    with patch("app.settings.panels.policy_repo._git_ls_remote", return_value=True), \
         patch("app.settings.panels.policy_repo.WorkingCopyManager") as mgr, \
         patch("app.settings.panels.policy_repo.GitHubProvider"):
        instance = mgr.return_value
        client.post("/htmx/settings/policy-repo/test/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
        response = client.post("/settings/policy-repo/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
    assert store.get("policy_repo.url") == "https://github.com/diocese/policies"
    assert store.get("policy_repo.branch") == "main"
    instance.sync.assert_called_once()


def test_disconnect_clears_store_and_removes_working_copy(client, admin, tmp_path, monkeypatch):
    client.force_login(admin)
    from app.credentials import store
    monkeypatch.setenv("POLICYCODEX_WORKING_COPY_ROOT", str(tmp_path / "wc"))
    (tmp_path / "wc").mkdir()
    (tmp_path / "wc" / "policies-repo").mkdir()
    store.set("policy_repo.url", "https://github.com/diocese/policies")
    store.set("policy_repo.branch", "main")
    response = client.post("/settings/policy-repo/", {
        "action": "disconnect",
        "confirm_token": "DISCONNECT",
    })
    assert not store.has("policy_repo.url")
    assert not (tmp_path / "wc" / "policies-repo").exists()


def test_policy_repo_panel_has_intro(client, admin):
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/x/y")
    store.set("policy_repo.branch", "main")
    client.force_login(admin)
    response = client.get("/settings/policy-repo/")
    body = response.content.decode()
    # An intro paragraph appears before the form.
    body_after_title = body[body.index("<h1"):]
    assert "<p" in body_after_title[:500]
