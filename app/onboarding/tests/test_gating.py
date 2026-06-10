"""DISC-03: onboarding gating signals (admin present, working copy present,
furthest_step, run in progress)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.mark.django_db
def test_no_admin_routes_anyone_to_screen_1():
    client = Client()
    response = client.get("/onboarding/", follow=False)
    assert response.status_code == 302
    assert response.url.endswith("/onboarding/admin-account/")


@pytest.mark.django_db
def test_with_admin_and_no_login_goes_to_login():
    User.objects.create_superuser("admin", "a@b.com", "pw")
    client = Client()
    response = client.get("/onboarding/", follow=False)
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_logged_in_admin_with_no_working_copy_stuck_before_screen_6(tmp_path):
    User.objects.create_superuser("admin", "a@b.com", "pw")
    client = Client()
    client.login(username="admin", password="pw")
    with patch("app.onboarding.views._working_copy_dir", return_value=tmp_path / "absent"):
        response = client.get("/onboarding/retention-policy/", follow=False)
    assert response.status_code == 302
    assert response.url.endswith("/onboarding/github-repo/")


@pytest.mark.skip(reason="DISC-11 lands the InventoryRun model")
@pytest.mark.django_db
def test_running_inventory_routes_to_inventory_page(tmp_path):
    pass
