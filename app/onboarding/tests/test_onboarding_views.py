"""Tests for the onboarding wizard views (APP-08)."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


def test_urls_resolve():
    assert reverse("onboarding") == "/onboarding/"
    assert reverse("onboarding_step", kwargs={"step": "github-repo"}) == "/onboarding/github-repo/"


def test_onboarding_requires_login(client):
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")


def test_root_redirects_to_first_step_when_fresh(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_get_step_renders_title_and_indicator(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "GitHub repository" in body
    assert "Step 1 of 7" in body


def test_unknown_step_returns_404(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/not-a-step/")
    assert resp.status_code == 404


def test_ahead_jump_is_gated(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/versioning/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"
