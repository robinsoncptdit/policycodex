"""DISC-12: inventory progress page. DISC-13: HTMX polling status endpoint."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

from app.inventory.models import InventoryRun, InventoryItem
from app.inventory.runner import start_run


@login_required
def inventory_page(request):
    # The inventory page now requires a configured working copy. If none
    # exists, redirect to catalog (which shows the "configure Settings"
    # banner). Task 28 will replace this with the top-level /inventory/
    # page from the Settings-page rebuild plan.
    try:
        working_dir = _working_dir_or_fail()
    except RuntimeError:
        return redirect("catalog")

    # Find or create the run.
    run = InventoryRun.objects.filter(status__in=("pending", "running")).first()
    if run is None and not InventoryRun.objects.filter(status="completed").exists():
        stage_dir = _stage_dir_or_fail()
        if stage_dir is None:
            return redirect("catalog")
        files = sorted(p for p in stage_dir.iterdir() if p.is_file() and p.name != "manifest.json")
        run = InventoryRun.objects.create(status="pending", total=len(files))
        for f in files:
            InventoryItem.objects.create(run=run, source_filename=f.name, status="pending")
        start_run(run, stage_dir, working_dir)
    elif run is None:
        # Run already completed — go straight to catalog.
        return redirect("catalog")

    return render(request, "inventory/inventory.html", {"run": run})


def _working_dir_or_fail() -> Path:
    """Return the working-copy directory. Should always be present at this point."""
    from app.working_copy.config import load_working_copy_config
    return load_working_copy_config().working_dir


def _stage_dir_or_fail():
    """Return the ingest staging directory if configured, else None."""
    import os
    root = os.environ.get("POLICYCODEX_INGEST_STAGING_ROOT")
    if not root:
        return None
    stage_root = Path(root)
    # Return the most recent run directory if any exist.
    dirs = sorted(stage_root.iterdir()) if stage_root.exists() else []
    return dirs[-1] if dirs else None


@login_required
def status_fragment(request):
    """DISC-13: HTMX polling target. Returns the cards-grid fragment, or
    HX-Redirect on completion. DISC-14 plugs finalize_after_inventory in
    on the completed branch. Task 28 will simplify finalize_after_inventory
    to drop the config_yaml_text / bundle_dir kwargs."""
    run_id_raw = request.GET.get("run", "0")
    try:
        run_id = int(run_id_raw)
    except ValueError:
        return HttpResponse(status=404)
    run = InventoryRun.objects.filter(pk=run_id).first()
    if run is None:
        return HttpResponse(status=404)
    if run.status == "completed":
        # DISC-14: open the single bulk PR on first completion poll.
        if not run.pr_url and not run.pr_error:
            from app.inventory.finalize import finalize_after_inventory
            try:
                working_dir = _working_dir_or_fail()
                # config_yaml_text and bundle_dir are legacy from the pre-pivot flow.
                # Task 28 simplifies finalize_after_inventory to (run, *, working_dir).
                bundle_dir = working_dir / "policies" / "document-retention"
                finalize_after_inventory(
                    run,
                    working_dir=working_dir,
                    config_yaml_text="",
                    bundle_dir=bundle_dir,
                )
            except Exception as exc:  # noqa: BLE001
                run.pr_error = str(exc)
                run.save()
        resp = HttpResponse("")
        resp["HX-Redirect"] = "/catalog/"
        return resp
    html = render_to_string("inventory/_inventory_status.html", {"run": run})
    return HttpResponse(html)
