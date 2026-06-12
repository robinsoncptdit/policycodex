import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.fixture
def editor(db):
    u = User.objects.create_user("ed", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Editor"))
    return u


def test_retry_item_resets_status(client, editor, tmp_path):
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(
        status="completed", total=2, completed=1, failed=1, stage_dir=str(tmp_path),
    )
    item = InventoryItem.objects.create(run=run, source_filename="x.pdf",
                                         status="failed", error_message="LLM 500")
    client.force_login(editor)
    with patch("app.inventory.views.start_run") as start:
        client.post(f"/inventory/item/{item.pk}/retry/")
    item.refresh_from_db()
    assert item.status == "pending"
    start.assert_called_once()


def test_retry_run_resets_all_items(client, editor, tmp_path):
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(
        status="failed", total=2, pr_error="x", stage_dir=str(tmp_path),
    )
    InventoryItem.objects.create(run=run, source_filename="a.pdf", status="failed")
    InventoryItem.objects.create(run=run, source_filename="b.pdf", status="failed")
    client.force_login(editor)
    with patch("app.inventory.views.start_run") as start:
        client.post(f"/inventory/run/{run.pk}/retry/")
    run.refresh_from_db()
    assert run.status == "pending"
    for item in run.items.all():
        assert item.status == "pending"
