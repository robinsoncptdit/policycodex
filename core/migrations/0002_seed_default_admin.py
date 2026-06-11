"""Seed admin/admin1234 on first boot. Idempotent."""
from django.contrib.auth.hashers import make_password
from django.db import migrations


def _seed(apps, schema_editor):
    if apps is not None:
        User = apps.get_model("auth", "User")
        UserProfile = apps.get_model("core", "UserProfile")
    else:
        from django.contrib.auth import get_user_model
        from core.models import UserProfile
        User = get_user_model()
    user, created = User.objects.get_or_create(
        username="admin",
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "email": "",
            "password": make_password("admin1234"),
        },
    )
    if created:
        UserProfile.objects.get_or_create(
            user=user, defaults={"must_change_password": True},
        )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_create_user_profile"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(_seed, _noop)]


# Exposed for tests that re-invoke the seed (idempotency check)
_seed_default_admin_callable = _seed
