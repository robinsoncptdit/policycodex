"""Tests for the catalog list view."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def test_catalog_url_resolves():
    assert reverse("catalog") == "/catalog/"


def test_catalog_requires_login(client):
    response = client.get("/catalog/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/catalog/" in response.url


def test_catalog_empty_state_when_repo_url_unset(client, user):
    client.force_login(user)
    with override_settings(POLICYCODEX_POLICY_REPO_URL=""):
        response = client.get("/catalog/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "No policies yet" in body
    # Onboarding hint should appear in the empty state.
    assert "pull_working_copy" in body or "onboarding" in body.lower()
