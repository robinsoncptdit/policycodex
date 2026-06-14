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
        return type("R", (), {"written": ["slug-a", "slug-b"], "failed": [], "pr": None})()

    with patch("app.inventory.runner.run_inventory_pass", side_effect=fake_pass):
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
    (stage / "a.pdf").write_text("x")
    working = tmp_path / "working"
    working.mkdir()

    run = InventoryRun.objects.create(status="pending", total=0)

    with patch("app.inventory.runner.run_inventory_pass", side_effect=RuntimeError("boom")):
        thread = start_run(run, stage, working)
        thread.join(timeout=5)

    run.refresh_from_db()
    assert run.status == "failed"
    assert "boom" in run.pr_error


@pytest.mark.django_db(transaction=True)
def test_runner_does_not_call_finalize_and_uses_orchestrator_pr_url(tmp_path):
    from app.inventory.models import InventoryRun
    from app.inventory.runner import start_run

    stage = tmp_path / "stage"; stage.mkdir(); (stage / "a.pdf").write_text("x")
    working = tmp_path / "working"; working.mkdir()
    run = InventoryRun.objects.create(status="pending", total=1)

    def fake_pass(*, manifest, **kwargs):
        return type("R", (), {"pr": {"url": "https://github.com/x/y/pull/7"}})()

    with (
        patch("app.inventory.runner.run_inventory_pass", side_effect=fake_pass),
        # Patch at the finalize module's source so a re-introduced lazy local
        # import (the pattern that was removed from _do_run) would still be caught.
        patch("app.inventory.finalize.finalize_after_inventory") as fin,
    ):
        thread = start_run(run, stage, working)
        thread.join(timeout=5)

    fin.assert_not_called()
    run.refresh_from_db()
    assert run.status == "completed"
    assert run.pr_url == "https://github.com/x/y/pull/7"


@pytest.mark.django_db(transaction=True)
def test_runner_passes_full_built_manifest_to_orchestrator(tmp_path):
    import app.inventory.runner as runner_mod
    from app.inventory.models import InventoryRun
    from app.inventory.runner import start_run

    stage = tmp_path / "stage"; stage.mkdir()
    (stage / "a.pdf").write_text("x"); (stage / "b.pdf").write_text("y")
    working = tmp_path / "working"; working.mkdir()
    run = InventoryRun.objects.create(status="pending", total=2)

    captured = {}
    def fake_pass(*, manifest, **kwargs):
        captured["names"] = sorted(e.path.name for e in manifest)
        return type("R", (), {"pr": None})()

    with patch("app.inventory.runner.run_inventory_pass", side_effect=fake_pass):
        thread = start_run(run, stage, working)
        thread.join(timeout=5)

    run.refresh_from_db()
    assert run.status == "completed"  # diagnostic: a silent manifest-build break surfaces here, not as KeyError below
    assert captured["names"] == ["a.pdf", "b.pdf"]
    # F9: the inert incremental layer is gone from the runner module.
    assert not hasattr(runner_mod, "plan_incremental_run")
