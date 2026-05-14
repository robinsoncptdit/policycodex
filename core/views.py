from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from app.working_copy.config import load_working_copy_config
from ingest.policy_reader import BundleAwarePolicyReader


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def catalog(request):
    """Render the policy inventory from the local working copy.

    Falls back to an empty-state template when the working copy is not
    yet configured (fresh install before onboarding) or not yet synced.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return render(request, "catalog.html", {"is_empty_onboarding": True, "policies": []})

    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return render(request, "catalog.html", {"is_empty_onboarding": True, "policies": []})

    policies = list(BundleAwarePolicyReader(policies_dir).read())
    return render(request, "catalog.html", {"is_empty_onboarding": False, "policies": policies})


def root_redirect(request):
    """Send the root URL `/` to `/catalog/`. `catalog` itself handles login_required."""
    return redirect("catalog")
