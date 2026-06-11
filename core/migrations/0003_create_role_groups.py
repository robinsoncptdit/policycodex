from django.db import migrations


def _create(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ("Viewer", "Editor", "Admin"):
        Group.objects.get_or_create(name=name)


def _delete(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=("Viewer", "Editor", "Admin")).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_seed_default_admin"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(_create, _delete)]
