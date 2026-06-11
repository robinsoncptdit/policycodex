"""DISC-12: inventory progress page."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

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
