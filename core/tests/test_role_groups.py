import pytest
from django.contrib.auth.models import Group


@pytest.mark.django_db
def test_three_role_groups_exist():
    assert Group.objects.filter(name="Viewer").exists()
    assert Group.objects.filter(name="Editor").exists()
    assert Group.objects.filter(name="Admin").exists()


@pytest.mark.django_db
def test_groups_have_no_permissions_in_v01():
    """v0.1 uses group membership as a coarse capability check, not Django's
    per-permission system. Reviewer/Publisher are v0.2; their permissions
    will hang off these groups later."""
    for name in ("Viewer", "Editor", "Admin"):
        assert Group.objects.get(name=name).permissions.count() == 0
