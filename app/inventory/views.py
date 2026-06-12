"""Inventory page: 5-state lifecycle + drop bucket + cards grid."""
from __future__ import annotations

from pathlib import Path
import os
import uuid

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from app.inventory.models import InventoryRun, InventoryItem
from app.inventory.runner import start_run
from app.working_copy.config import load_working_copy_config
from core.permissions import require_role


_ALLOWED_EXT = {".pdf", ".docx", ".md", ".txt"}
_MAX_FILE_BYTES = 25 * 1024 * 1024
_MAX_TOTAL_BYTES = 500 * 1024 * 1024


def _staging_root() -> Path:
    raw = os.environ.get("POLICYCODEX_INGEST_STAGING_ROOT", "")
    return Path(raw) if raw else Path("/data/ingest-staging")


def _latest_run() -> InventoryRun | None:
    return InventoryRun.objects.order_by("-started_at").first()


def _lifecycle(run: InventoryRun | None) -> str:
    if run is None:
        return "empty"
    if run.status in ("pending", "running"):
        return "active"
    if run.status == "failed":
        return "failed"
    if run.failed > 0:
        return "completed_with_failures"
    return "completed"


@require_role("Editor")
def inventory_page(request):
    run = _latest_run()
    return render(request, "inventory/inventory.html", {
        "run": run,
        "lifecycle": _lifecycle(run),
    })


@require_role("Editor")
@require_POST
def inventory_upload(request):
    run = _latest_run()
    files = request.FILES.getlist("files")
    if not files:
        return render(request, "inventory/inventory.html", {
            "run": run,
            "lifecycle": _lifecycle(run),
            "error": "Drop at least one document.",
        })
    err = _validate(files)
    if err:
        return render(request, "inventory/inventory.html", {
            "run": run,
            "lifecycle": _lifecycle(run),
            "error": err,
        })
    # Reject if a run is already active.
    if run and run.status in ("pending", "running"):
        return render(request, "inventory/inventory.html", {
            "run": run,
            "lifecycle": "active",
            "error": "A run is already in progress.",
        })
    run_id = uuid.uuid4().hex[:12]
    stage_dir = _staging_root() / run_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        with (stage_dir / f.name).open("wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)
    run = InventoryRun.objects.create(
        status="pending", total=len(files), stage_dir=str(stage_dir),
    )
    for f in files:
        InventoryItem.objects.create(run=run, source_filename=f.name, status="pending")
    try:
        working_dir = load_working_copy_config().working_dir
    except RuntimeError:
        run.status = "failed"
        run.pr_error = "Policy repository not configured."
        run.save()
        return redirect("inventory")
    start_run(run, stage_dir, working_dir)
    return redirect("inventory")


def _validate(files):
    total = 0
    for f in files:
        ext = Path(f.name).suffix.lower()
        if ext not in _ALLOWED_EXT:
            return f"Unsupported file type: {f.name}"
        if f.size > _MAX_FILE_BYTES:
            return f"File too large: {f.name} (limit 25 MB)"
        total += f.size
    if total > _MAX_TOTAL_BYTES:
        return "Total upload too large (limit 500 MB)."
    return None


@require_role("Editor")
def status_fragment(request):
    """HTMX polling endpoint. Returns the cards grid + status strip."""
    run_id = request.GET.get("run")
    run = InventoryRun.objects.filter(pk=run_id).first()
    if run is None:
        return HttpResponse(status=404)
    return HttpResponse(render_to_string("inventory/_status.html", {
        "run": run,
        "lifecycle": _lifecycle(run),
    }, request=request))


@require_role("Editor")
@require_POST
def retry_item(request, item_id):
    item = InventoryItem.objects.filter(pk=item_id).first()
    if item is None:
        return HttpResponse(status=404)
    item.status = "pending"
    item.error_message = ""
    item.save()
    run = item.run
    if not run.stage_dir:
        return HttpResponse("Retry unavailable: staging directory unknown.", status=400)
    try:
        working_dir = load_working_copy_config().working_dir
        start_run(run, Path(run.stage_dir), working_dir)
    except Exception as exc:  # noqa: BLE001
        return HttpResponse(f"Retry failed: {exc}", status=500)
    return redirect("inventory")


@require_role("Editor")
@require_POST
def retry_run(request, run_id):
    run = InventoryRun.objects.filter(pk=run_id).first()
    if run is None:
        return HttpResponse(status=404)
    if not run.stage_dir:
        return HttpResponse("Retry unavailable: staging directory unknown.", status=400)
    run.status = "pending"
    run.pr_error = ""
    run.save()
    run.items.all().update(status="pending", error_message="")
    try:
        working_dir = load_working_copy_config().working_dir
        start_run(run, Path(run.stage_dir), working_dir)
    except Exception as exc:  # noqa: BLE001
        return HttpResponse(f"Retry failed: {exc}", status=500)
    return redirect("inventory")
