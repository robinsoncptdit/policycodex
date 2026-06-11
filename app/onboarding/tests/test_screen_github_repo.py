"""DISC-07: Screen 4 github-repo connects/creates and clones the working copy."""
from __future__ import annotations

from pathlib import Path
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
    # Pre-seed wizard state so gating Signal 3 allows reaching github-repo (index 3)
    from app.onboarding.state import SESSION_KEY
    session = c.session
    session[SESSION_KEY] = {
        "current_step": "github-repo",
        "completed": ["admin-account", "github-app", "llm-provider"],
        "data": {},
    }
    session.save()
    return c


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from app.credentials import store
    k = tmp_path / ".credential-key"
    k.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(k))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")


def test_get_renders_form(logged_in_admin):
    r = logged_in_admin.get("/onboarding/github-repo/")
    assert r.status_code == 200
    assert b"repository" in r.content.lower()


def test_connect_existing_clones_working_copy(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_WORKING_COPY_ROOT", str(tmp_path / "wc"))
    with patch("app.working_copy.manager.WorkingCopyManager.sync") as sync:
        sync.return_value = Path(tmp_path / "wc" / "policies-repo")
        r = logged_in_admin.post("/onboarding/github-repo/", {
            "action": "continue",
            "mode": "connect",
            "repo_url": "https://github.com/acme/policies",
            "branch": "main",
        })
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/configuration/")
    sync.assert_called_once()


def test_create_new_creates_repo_then_clones(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_WORKING_COPY_ROOT", str(tmp_path / "wc"))
    with patch("app.git_provider.github_provider.GitHubProvider.create_repository", return_value={"clone_url": "https://github.com/acme/new.git"}) as create, \
         patch("app.working_copy.manager.WorkingCopyManager.sync") as sync:
        sync.return_value = Path(tmp_path / "wc" / "new")
        r = logged_in_admin.post("/onboarding/github-repo/", {
            "action": "continue",
            "mode": "create",
            "org": "acme",
            "repo_name": "new",
            "branch": "main",
        })
    assert r.status_code == 302
    create.assert_called_once_with(org="acme", repo_name="new", private=True)


def test_clone_failure_renders_error(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_WORKING_COPY_ROOT", str(tmp_path / "wc"))
    with patch("app.working_copy.manager.WorkingCopyManager.sync", side_effect=RuntimeError("could not clone: 404 Not Found")):
        r = logged_in_admin.post("/onboarding/github-repo/", {
            "action": "continue",
            "mode": "connect",
            "repo_url": "https://github.com/acme/nope",
            "branch": "main",
        })
    assert r.status_code == 200
    assert b"could not clone" in r.content.lower()
