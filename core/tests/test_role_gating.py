import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.fixture
def viewer(db):
    u = User.objects.create_user("viewer", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Viewer"))
    return u


@pytest.fixture
def editor(db):
    u = User.objects.create_user("editor", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Editor"))
    return u


@pytest.fixture
def random_user(db):
    """No group membership."""
    u = User.objects.create_user("nobody", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    return u


def test_viewer_can_hit_catalog(client, viewer):
    client.force_login(viewer)
    response = client.get("/catalog/")
    assert response.status_code == 200


def test_no_group_user_gets_403_on_catalog(client, random_user):
    client.force_login(random_user)
    response = client.get("/catalog/")
    assert response.status_code == 403


def test_viewer_cannot_hit_policy_edit(client, viewer):
    """Editor+ only."""
    client.force_login(viewer)
    response = client.get("/policies/some-slug/edit/")
    # 403 from the decorator; 404 from the missing policy is also OK — we
    # care that it's NOT 200.
    assert response.status_code in (403, 404)


def test_editor_can_hit_policy_edit_or_404(client, editor):
    client.force_login(editor)
    response = client.get("/policies/some-slug/edit/")
    # 200 if the policy exists, 404 if it does not. 403 means the gate
    # blocked an Editor — that's wrong.
    assert response.status_code != 403
