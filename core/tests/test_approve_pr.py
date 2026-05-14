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
