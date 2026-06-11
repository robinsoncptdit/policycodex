"""DISC-11: background-thread wrapper around ai.inventory.run_inventory_pass.

Per-item status updates flow back via the on_item_done callback the orchestrator
calls as each policy completes; we translate those into row updates on the
matching InventoryItem.

start_run(run, stage_dir, working_dir, **pass_kwargs) accepts an explicit
working_dir so the DISC-12 view can supply it from WorkingCopyConfig. Deriving
it from stage_dir would be fragile and environment-dependent.

Keyword arguments for the orchestrator (provider, llm_provider, taxonomy,
author_name, author_email, base_branch) are forwarded verbatim, keeping the
runner thin and letting the caller wire up the per-diocese dependencies.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from ai.inventory import run_inventory_pass
from ingest.incremental import plan_incremental_run

from app.inventory.models import InventoryItem, InventoryRun


def _on_item_done(run_id: int):
    def cb(*, source, slug, title, classification, confidence):
        with transaction.atomic():
            run = InventoryRun.objects.select_for_update().get(pk=run_id)
            item = InventoryItem.objects.filter(run=run, source_filename=source).first()
            if item is None:
                return
            item.slug = slug
            item.title = title
            item.classification = classification
            item.confidence = confidence
            item.status = "done"
            item.save()
            run.completed = run.items.filter(status="done").count()
            run.failed = run.items.filter(status="failed").count()
            run.save()
    return cb


def _on_item_failed(run_id: int):
    def cb(*, source, error):
        with transaction.atomic():
            run = InventoryRun.objects.select_for_update().get(pk=run_id)
            item = InventoryItem.objects.filter(run=run, source_filename=source).first()
            if item:
                item.status = "failed"
                item.error_message = error
                item.save()
                run.failed = run.items.filter(status="failed").count()
                run.save()
    return cb


def _do_run(run_id: int, stage_dir: Path, working_dir: Path, pass_kwargs: dict[str, Any]):
    # Each new thread needs its own Django DB connection; close any stale
    # inherited handles so Django opens a fresh one on first query.
    from django.db import close_old_connections
    close_old_connections()

    InventoryRun.objects.filter(pk=run_id).update(status="running")
    try:
        diff = plan_incremental_run(stage_dir, manifest_path=stage_dir / "manifest.json")
        run_inventory_pass(
            manifest=diff.to_process,
            working_dir=working_dir,
            on_item_done=_on_item_done(run_id),
            on_item_failed=_on_item_failed(run_id),
            **pass_kwargs,
        )
        InventoryRun.objects.filter(pk=run_id).update(
            status="completed", completed_at=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001
        InventoryRun.objects.filter(pk=run_id).update(
            status="failed", pr_error=str(exc),
        )
        # Do not re-raise: the status row records the failure; a daemon thread
        # has no caller to catch this, so re-raising would just produce noise
        # in the unhandled-thread-exception log.


def start_run(
    run: InventoryRun,
    stage_dir: Path,
    working_dir: Path,
    **pass_kwargs: Any,
) -> threading.Thread:
    """Launch the inventory pass in a daemon thread.

    Args:
        run: The InventoryRun row to track progress on.
        stage_dir: Directory containing the uploaded source documents.
        working_dir: The diocese's local working copy root (parent of ``policies/``).
        **pass_kwargs: Forwarded verbatim to ``run_inventory_pass`` (provider,
            llm_provider, taxonomy, author_name, author_email, base_branch, etc.).
    """
    thread = threading.Thread(
        target=_do_run, args=(run.pk, stage_dir, working_dir, pass_kwargs),
        name=f"inventory-run-{run.pk}", daemon=True,
    )
    thread.start()
    return thread
