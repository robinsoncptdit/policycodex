import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.fixture
def admin(db):
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


def test_get_renders_users_table(client, admin):
    client.force_login(admin)
    response = client.get("/settings/users/")
    assert response.status_code == 200
    assert b"admin" in response.content
    assert b"Add user" in response.content


def test_add_user_creates_with_must_change_true(client, admin):
    client.force_login(admin)
    response = client.post("/settings/users/", {
        "action": "add",
        "username": "alice",
        "email": "alice@example.com",
        "role": "Editor",
    })
    alice = User.objects.get(username="alice")
    assert alice.profile.must_change_password is True
    assert alice.groups.filter(name="Editor").exists()


def test_add_user_displays_temp_password_once(client, admin):
    client.force_login(admin)
    response = client.post("/settings/users/", {
        "action": "add",
        "username": "bob",
        "email": "",
        "role": "Viewer",
    })
    assert b"temporary password" in response.content.lower()


def test_change_role_moves_user_between_groups(client, admin):
    client.force_login(admin)
    user = User.objects.create_user("carol", password="x")
    user.groups.add(Group.objects.get(name="Viewer"))
    client.post("/settings/users/", {
        "action": "change_role",
        "user_id": str(user.pk),
        "role": "Editor",
    })
    user.refresh_from_db()
    assert user.groups.filter(name="Editor").exists()
    assert not user.groups.filter(name="Viewer").exists()


def test_delete_user_succeeds(client, admin):
    client.force_login(admin)
    user = User.objects.create_user("dave", password="x")
    client.post("/settings/users/", {
        "action": "delete",
        "user_id": str(user.pk),
        "confirm_token": "DELETE dave",
    })
    assert not User.objects.filter(username="dave").exists()


def test_cannot_delete_last_superuser(client, admin):
    client.force_login(admin)
    response = client.post("/settings/users/", {
        "action": "delete",
        "user_id": str(admin.pk),
        "confirm_token": "DELETE admin",
    })
    assert User.objects.filter(username="admin").exists()
    assert response.status_code == 200
    assert b"last administrator" in response.content.lower()


def test_users_panel_has_intro(client, admin):
    client.force_login(admin)
    response = client.get("/settings/users/")
    body = response.content.decode()
    # An intro paragraph appears before the user table.
    assert "Viewer" in body and "Editor" in body and "Admin" in body
    body_after_title = body[body.index("<h1"):]
    assert "<p" in body_after_title[:500]
