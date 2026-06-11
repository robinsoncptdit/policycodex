"""UserProfile + default must_change_password=True for every new user."""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_save_auto_creates_profile_with_must_change_password_true():
    user = User.objects.create_user(username="alice", password="x")
    assert user.profile.must_change_password is True


@pytest.mark.django_db
def test_existing_user_can_be_marked_password_changed():
    user = User.objects.create_user(username="bob", password="x")
    user.profile.must_change_password = False
    user.profile.save()
    user.refresh_from_db()
    assert user.profile.must_change_password is False


@pytest.mark.django_db
def test_two_users_have_independent_profiles():
    u1 = User.objects.create_user(username="u1", password="x")
    u2 = User.objects.create_user(username="u2", password="x")
    u1.profile.must_change_password = False
    u1.profile.save()
    assert u2.profile.must_change_password is True
