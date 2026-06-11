"""DISC-12: inventory progress page. DISC-13: HTMX polling status endpoint."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

from app.inventory.models import InventoryRun, InventoryItem
from app.inventory.runner import start_run
from app.onboarding.state import WizardState


@login_required
def inventory_page(request):
    state = WizardState(request.session)
    pd = state.get_data("policy-documents")
    if not pd:
        return redirect("onboarding_step", step="policy-documents")

    # Find or create the run.
    run = InventoryRun.objects.filter(status__in=("pending", "running")).first()
    if run is None and not InventoryRun.objects.filter(status="completed").exists():
        stage_dir = Path(pd["stage_dir"])
        files = sorted(p for p in stage_dir.iterdir() if p.is_file() and p.name != "manifest.json")
        run = InventoryRun.objects.create(status="pending", total=len(files))
        for f in files:
            InventoryItem.objects.create(run=run, source_filename=f.name, status="pending")
        # Derive working_dir from the working-copy config.
        working_dir = _working_dir_or_fail()
        start_run(run, stage_dir, working_dir)
    elif run is None:
        # Run already completed — go straight to catalog.
        return redirect("catalog")

    return render(request, "onboarding/inventory.html", {"run": run})


def _working_dir_or_fail() -> Path:
    """Return the working-copy directory. Should always be present at this point."""
    from app.working_copy.config import load_working_copy_config
    return load_working_copy_config().working_dir


@login_required
def status_fragment(request):
    """DISC-13: HTMX polling target. Returns the cards-grid fragment, or
    HX-Redirect on completion. DISC-14 will plug finalize_after_inventory in
    on the completed branch; until then, completion just redirects to /catalog/."""
    run_id_raw = request.GET.get("run", "0")
    try:
        run_id = int(run_id_raw)
    except ValueError:
        return HttpResponse(status=404)
    run = InventoryRun.objects.filter(pk=run_id).first()
    if run is None:
        return HttpResponse(status=404)
    if run.status == "completed":
        # DISC-14 will call finalize_after_inventory here (single bulk PR).
        # For DISC-13, just redirect to /catalog/.
        try:
            from app.inventory.finalize import finalize_after_inventory
            if not run.pr_url and not run.pr_error:
                try:
                    finalize_after_inventory(run)
                except Exception as exc:  # noqa: BLE001
                    run.pr_error = str(exc)
                    run.save()
        except ImportError:
            # DISC-14 hasn't landed yet; that's fine for DISC-13 — completion
            # just sends the user to /catalog/.
            pass
        resp = HttpResponse("")
        resp["HX-Redirect"] = "/catalog/"
        return resp
    html = render_to_string("onboarding/_inventory_status.html", {"run": run})
    return HttpResponse(html)
