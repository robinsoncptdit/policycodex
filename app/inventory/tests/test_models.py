"""DISC-11: InventoryRun + InventoryItem."""
import pytest


@pytest.mark.django_db
def test_inventory_run_defaults():
    from app.inventory.models import InventoryRun
    run = InventoryRun.objects.create(status="pending", total=5)
    assert run.completed == 0
    assert run.failed == 0
    assert run.pr_url == ""


@pytest.mark.django_db
def test_inventory_item_belongs_to_run():
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(status="pending", total=1)
    item = InventoryItem.objects.create(run=run, source_filename="x.pdf", status="pending")
    assert item.run == run
    assert run.items.count() == 1
