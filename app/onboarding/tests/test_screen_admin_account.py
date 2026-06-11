"""DISC-04: Screen 1 admin-account."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.mark.django_db
def test_get_renders_when_no_admin_exists():
    client = Client()
    response = client.get("/onboarding/admin-account/")
    assert response.status_code == 200
    assert b"admin account" in response.content.lower()


@pytest.mark.django_db
def test_get_redirects_when_admin_exists_and_not_logged_in():
    User.objects.create_superuser("admin", "a@b.com", "pw")
    client = Client()
    response = client.get("/onboarding/admin-account/", follow=False)
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_post_creates_superuser_and_logs_them_in():
    client = Client()
    response = client.post("/onboarding/admin-account/", {
        "action": "continue",
        "username": "first-admin",
        "email": "admin@diocese.example",
        "password": "rare-fox-thunder-7",
        "password_confirm": "rare-fox-thunder-7",
    }, follow=False)
    assert response.status_code == 302
    assert response.url.endswith("/onboarding/github-app/")
    assert User.objects.filter(username="first-admin", is_superuser=True).exists()
    # The session now holds the new admin.
    response_next = client.get("/onboarding/github-app/")
    assert response_next.status_code == 200


@pytest.mark.django_db
def test_password_mismatch_returns_form_with_error():
    client = Client()
    response = client.post("/onboarding/admin-account/", {
        "action": "continue",
        "username": "x",
        "email": "x@y.com",
        "password": "abcdefghij",
        "password_confirm": "DIFFERENT123",
    })
    assert response.status_code == 200
    assert b"Passwords do not match" in response.content


@pytest.mark.django_db
def test_short_password_returns_form_with_error():
    client = Client()
    response = client.post("/onboarding/admin-account/", {
        "action": "continue",
        "username": "x",
        "email": "x@y.com",
        "password": "short",
        "password_confirm": "short",
    })
    assert response.status_code == 200
    assert b"at least 8" in response.content.lower()
