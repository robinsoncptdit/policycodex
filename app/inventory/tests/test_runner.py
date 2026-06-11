"""DISC-11: runner wraps ai.inventory.run_inventory_pass with row updates."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.django_db(transaction=True)
def test_runner_marks_items_done_as_orchestrator_completes(tmp_path):
    from app.inventory.models import InventoryItem, InventoryRun
    from app.inventory.runner import start_run

    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "a.pdf").write_text("x")
    (stage / "b.pdf").write_text("y")

    working = tmp_path / "working"
    working.mkdir()

    run = InventoryRun.objects.create(status="pending", total=2)
    InventoryItem.objects.create(run=run, source_filename="a.pdf", status="pending")
    InventoryItem.objects.create(run=run, source_filename="b.pdf", status="pending")

    def fake_pass(*, manifest, **kwargs):
        cb = kwargs["on_item_done"]
        for entry in manifest:
            cb(
                source=entry.path.name,
                slug="slug-" + entry.path.stem,
                title="Title " + entry.path.stem,
                classification="HR-001",
                confidence=0.9,
            )
        return type("R", (), {"written": ["slug-a", "slug-b"], "failed": []})()

    fake_entry_a = type("E", (), {"path": stage / "a.pdf"})()
    fake_entry_b = type("E", (), {"path": stage / "b.pdf"})()

    with (
        patch("app.inventory.runner.run_inventory_pass", side_effect=fake_pass),
        patch("app.inventory.runner.plan_incremental_run") as plan,
    ):
        plan.return_value = type("D", (), {
            "to_process": [fake_entry_a, fake_entry_b],
            "current": [],
            "removed": [],
        })()
        thread = start_run(run, stage, working)
        thread.join(timeout=5)

    run.refresh_from_db()
    assert run.status == "completed"
    assert run.completed == 2
    for item in run.items.all():
        assert item.status == "done"
        assert item.title.startswith("Title ")


@pytest.mark.django_db(transaction=True)
def test_runner_marks_run_failed_on_exception(tmp_path):
    from app.inventory.models import InventoryRun
    from app.inventory.runner import start_run

    stage = tmp_path / "stage"
    stage.mkdir()
    working = tmp_path / "working"
    working.mkdir()

    run = InventoryRun.objects.create(status="pending", total=0)

    with (
        patch("app.inventory.runner.run_inventory_pass", side_effect=RuntimeError("boom")),
        patch("app.inventory.runner.plan_incremental_run") as plan,
    ):
        plan.return_value = type("D", (), {"to_process": [], "current": [], "removed": []})()
        thread = start_run(run, stage, working)
        thread.join(timeout=5)

    run.refresh_from_db()
    assert run.status == "failed"
    assert "boom" in run.pr_error
