import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    # The seeded admin already exists; reuse it.
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


@pytest.fixture
def viewer(db):
    from django.contrib.auth.models import Group
    u = User.objects.create_user("viewer", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Viewer"))
    return u


def test_settings_root_redirects_to_first_panel(client, admin):
    client.force_login(admin)
    response = client.get("/settings/", follow=False)
    assert response.status_code == 302
    # First panel slug — github-app per the spec's nav order.
    assert response.url == "/settings/github-app/"


def test_unknown_slug_404s(client, admin):
    client.force_login(admin)
    response = client.get("/settings/does-not-exist/")
    assert response.status_code == 404


def test_non_admin_gets_403(client, viewer):
    client.force_login(viewer)
    response = client.get("/settings/github-app/")
    assert response.status_code == 403


def test_unauthenticated_bounces_to_login(client):
    response = client.get("/settings/github-app/", follow=False)
    assert response.status_code == 302
    assert "/login/" in response.url


def test_panel_render_called_on_get(client, admin):
    """The dispatch invokes the panel's render() for GET."""
    from django.http import HttpResponse
    client.force_login(admin)
    with patch("app.settings.registry.get_panel") as gp:
        panel = MagicMock()
        panel.can_access.return_value = True
        panel.render.return_value = HttpResponse("<html>X</html>", status=200)
        gp.return_value = panel
        response = client.get("/settings/github-app/")
    panel.render.assert_called_once()


def test_panel_save_called_on_post(client, admin):
    from django.http import HttpResponse
    client.force_login(admin)
    with patch("app.settings.registry.get_panel") as gp:
        panel = MagicMock()
        panel.can_access.return_value = True
        panel.save.return_value = HttpResponse("ok", status=200)
        gp.return_value = panel
        client.post("/settings/github-app/", {"action": "save"})
    panel.save.assert_called_once()
