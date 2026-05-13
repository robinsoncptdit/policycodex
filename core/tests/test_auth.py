"""Tests for APP-02 login/logout wiring."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="alice",
        password="hunter2hunter2",
        email="alice@example.com",
        first_name="Alice",
        last_name="Anderson",
    )


def test_login_get_returns_200_and_renders_form(client):
    response = client.get("/login/")
    assert response.status_code == 200
    # Spartan smoke check: the form fields are present.
    body = response.content.decode()
    assert 'name="username"' in body
    assert 'name="password"' in body


def test_login_url_resolves_via_name(client):
    """The 'login' URL name (used by @login_required redirects) resolves."""
    assert reverse("login") == "/login/"


def test_login_post_valid_credentials_redirects_to_redirect_url(client, user, settings):
    response = client.post(
        "/login/",
        {"username": "alice", "password": "hunter2hunter2"},
    )
    assert response.status_code == 302
    assert response.url == settings.LOGIN_REDIRECT_URL


def test_login_post_invalid_credentials_rerenders_with_error(client, user):
    response = client.post(
        "/login/",
        {"username": "alice", "password": "wrong-password"},
    )
    # Django's LoginView re-renders the form (200) with the form bound and
    # marked invalid; it does NOT redirect.
    assert response.status_code == 200
    form = response.context["form"]
    assert not form.is_valid()
    assert form.errors  # non-empty error dict


def test_login_post_missing_fields_rerenders_with_error(client):
    response = client.post("/login/", {})
    assert response.status_code == 200
    assert not response.context["form"].is_valid()


def test_logout_redirects_to_login(client, user):
    client.force_login(user)
    # Django's LogoutView requires POST for security.
    response = client.post("/logout/")
    assert response.status_code == 302
    assert response.url == "/login/"


def test_logout_clears_session(client, user):
    client.force_login(user)
    # Sanity: we're logged in before logout.
    assert "_auth_user_id" in client.session
    client.post("/logout/")
    assert "_auth_user_id" not in client.session
