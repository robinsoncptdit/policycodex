"""Tests for the APP-18 approve_pr view."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def test_approve_pr_url_resolves():
    assert reverse("approve_pr") == "/policies/approve/"


def test_approve_pr_requires_login(client):
    """An anonymous POST is redirected to the login page."""
    response = client.post("/policies/approve/", {"pr_number": "42"})
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/approve/" in response.url


def test_approve_pr_rejects_get(client, user):
    """GET is not allowed (405); the action mutates state and is POST-only."""
    client.force_login(user)
    response = client.get("/policies/approve/")
    assert response.status_code == 405


def test_approve_pr_rejects_missing_pr_number(client, user):
    """A POST without pr_number redirects with a messages.error flash."""
    client.force_login(user)
    response = client.post("/policies/approve/", {})
    assert response.status_code == 302
    assert response.url == "/catalog/"
    # The flash message is stored on the session-backed messages framework
    # and is delivered on the NEXT request (follow=True surfaces it).
    follow = client.get("/catalog/")
    body = follow.content.decode()
    assert "pr_number" in body.lower() or "missing" in body.lower()


def test_approve_pr_rejects_non_numeric_pr_number(client, user):
    """A non-integer pr_number is rejected with a messages.error flash."""
    client.force_login(user)
    response = client.post("/policies/approve/", {"pr_number": "not-a-number"})
    assert response.status_code == 302
    assert response.url == "/catalog/"


@pytest.mark.parametrize("bad_value", ["0", "-1", "-5"])
def test_approve_pr_rejects_non_positive_pr_number(client, user, bad_value):
    """PR number must be positive. HTML `min="1"` is client-side only;
    server-side guard rejects 0 and negative integers before reaching
    the provider (which would otherwise issue a confusing PyGithub 404)."""
    client.force_login(user)
    response = client.post("/policies/approve/", {"pr_number": bad_value})
    assert response.status_code == 302
    assert response.url == "/catalog/"


def test_approve_pr_happy_path_calls_provider_and_flashes_success(client, user, caplog):
    """Drafted PR + valid pr_number leads to provider.approve_pr being called with success flash."""
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = "drafted"
    fake_provider.approve_pr.return_value = {
        "review_id": 555,
        "state": "APPROVED",
        "pr_number": 42,
    }
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            with caplog.at_level("INFO", logger="core.views"):
                response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.read_pr_state.assert_called_once_with(42, "/tmp/wc")
    fake_provider.approve_pr.assert_called_once_with(
        pr_number=42, working_dir="/tmp/wc", body=""
    )
    # Audit log line includes the Django username + the PR number.
    log_text = " ".join(r.message for r in caplog.records)
    assert "reviewer" in log_text
    assert "42" in log_text
    # Success message is surfaced on the next request.
    follow = client.get("/catalog/")
    assert "approved" in follow.content.decode().lower()


@pytest.mark.parametrize("state", ["reviewed", "published", "closed"])
def test_approve_pr_refuses_non_drafted_state(client, user, state):
    """Already-approved, merged, or closed PRs cannot be approved again."""
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = state
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.approve_pr.assert_not_called()
    follow = client.get("/catalog/")
    body = follow.content.decode().lower()
    assert state in body or "cannot be approved" in body


def test_approve_pr_when_working_copy_unconfigured_flashes_error(client, user):
    """If load_working_copy_config raises, the view flashes an error and redirects."""
    client.force_login(user)
    with patch("core.views.load_working_copy_config", side_effect=RuntimeError("repo url unset")):
        response = client.post("/policies/approve/", {"pr_number": "42"})
    assert response.status_code == 302
    assert response.url == "/catalog/"
    follow = client.get("/catalog/")
    body = follow.content.decode().lower()
    assert "working copy" in body or "not configured" in body


def test_approve_pr_provider_exception_flashes_error(client, user):
    """If provider.approve_pr raises, the view flashes the error and redirects."""
    from github import GithubException
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = "drafted"
    fake_provider.approve_pr.side_effect = GithubException(
        status=403, data={"message": "Resource not accessible"}, headers={}
    )
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    follow = client.get("/catalog/")
    assert "error" in follow.content.decode().lower() or "could not approve" in follow.content.decode().lower()
