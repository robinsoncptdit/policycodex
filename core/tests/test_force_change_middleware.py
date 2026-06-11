import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_must_change(db):
    user = User.objects.create_user(username="alice", password="x")
    user.profile.must_change_password = True
    user.profile.save()
    return user


@pytest.fixture
def user_changed(db):
    user = User.objects.create_user(username="bob", password="x")
    user.profile.must_change_password = False
    user.profile.save()
    return user


@pytest.mark.skip("Task 6 wires password_change URL")
def test_must_change_user_hitting_catalog_redirects_to_change(client, user_must_change):
    client.force_login(user_must_change)
    response = client.get("/catalog/")
    assert response.status_code == 302
    assert response.url.startswith("/accounts/password/change/")
    assert "next=/catalog/" in response.url


def test_already_changed_user_passes_through(client, user_changed):
    client.force_login(user_changed)
    response = client.get("/catalog/", follow=False)
    assert response.status_code != 302 or "/accounts/password/change/" not in response.url


@pytest.mark.skip("Task 6 wires password_change URL")
def test_must_change_user_can_reach_change_page_itself(client, user_must_change):
    client.force_login(user_must_change)
    response = client.get("/accounts/password/change/")
    assert response.status_code == 200


def test_must_change_user_can_reach_logout(client, user_must_change):
    client.force_login(user_must_change)
    response = client.get("/logout/", follow=False)
    assert response.status_code != 302 or "/accounts/password/change/" not in response.url


def test_unauthenticated_user_unaffected(client):
    response = client.get("/catalog/", follow=False)
    # Catalog @login_required bounces to /login/, not to /accounts/password/change/.
    assert response.status_code == 302
    assert "/login/" in response.url
