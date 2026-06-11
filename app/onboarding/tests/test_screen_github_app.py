"""DISC-05: Screen 2 github-app credentials + Test Connection."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()
_VALID_PEM = "-----BEGIN PRIVATE KEY-----\nFAKEKEY\n-----END PRIVATE KEY-----"


@pytest.fixture
def logged_in_admin(db):
    user = User.objects.create_superuser("admin", "a@b.com", "pw")
    client = Client()
    client.login(username="admin", password="pw")
    # Pre-seed wizard state: admin-account complete, current=github-app.
    # Without this, gating Signal 3 bounces back to admin-account.
    from app.onboarding.state import SESSION_KEY
    session = client.session
    session[SESSION_KEY] = {
        "current_step": "github-app",
        "completed": ["admin-account"],
        "data": {},
    }
    session.save()
    return client


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


def test_get_renders_form(logged_in_admin):
    response = logged_in_admin.get("/onboarding/github-app/")
    assert response.status_code == 200
    assert b"App ID" in response.content


def test_test_connection_success_returns_green_fragment(logged_in_admin):
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials", return_value=True):
        response = logged_in_admin.post("/htmx/onboarding/github-app/test/", {
            "app_id": "123",
            "installation_id": "456",
            "private_key_pem": _VALID_PEM,
        })
    assert response.status_code == 200
    assert b"data-state=\"ok\"" in response.content


def test_test_connection_failure_returns_red_fragment(logged_in_admin):
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials", side_effect=RuntimeError("401 Bad credentials")):
        response = logged_in_admin.post("/htmx/onboarding/github-app/test/", {
            "app_id": "123",
            "installation_id": "456",
            "private_key_pem": _VALID_PEM,
        })
    assert response.status_code == 200
    assert b"data-state=\"error\"" in response.content
    assert b"401 Bad credentials" in response.content


def test_continue_without_passing_test_blocks(logged_in_admin):
    response = logged_in_admin.post("/onboarding/github-app/", {
        "action": "continue",
        "app_id": "123",
        "installation_id": "456",
        "private_key_pem": _VALID_PEM,
    })
    assert response.status_code == 200
    assert b"Test the connection first" in response.content


def test_continue_after_passing_test_advances(logged_in_admin):
    from app.credentials import store
    with patch("app.git_provider.github_provider.GitHubProvider.test_credentials", return_value=True):
        logged_in_admin.post("/htmx/onboarding/github-app/test/", {
            "app_id": "123",
            "installation_id": "456",
            "private_key_pem": _VALID_PEM,
        })
        response = logged_in_admin.post("/onboarding/github-app/", {
            "action": "continue",
            "app_id": "123",
            "installation_id": "456",
            "private_key_pem": _VALID_PEM,
        })
    assert response.status_code == 302
    assert response.url.endswith("/onboarding/llm-provider/")
    assert store.get("github_app.app_id") == "123"
    assert store.get("github_app.installation_id") == "456"
    assert store.get("github_app.private_key_pem") == _VALID_PEM
