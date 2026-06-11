import pytest
from django.contrib.auth import get_user_model

from core.models import UserProfile

User = get_user_model()


@pytest.mark.django_db
def test_seeded_admin_exists_after_migrate():
    admin = User.objects.filter(username="admin").first()
    assert admin is not None
    assert admin.is_superuser is True
    assert admin.check_password("admin1234") is True
    assert admin.profile.must_change_password is True


@pytest.mark.django_db
def test_seeded_admin_not_recreated_when_present():
    admin = User.objects.get(username="admin")
    admin.set_password("new-stronger-password-2026")
    admin.profile.must_change_password = False
    admin.profile.save()
    admin.save()
    from core.migrations import _seed_default_admin_callable as forward
    forward(None, None)
    admin.refresh_from_db()
    assert admin.check_password("new-stronger-password-2026")
    assert UserProfile.objects.get(user=admin).must_change_password is False
