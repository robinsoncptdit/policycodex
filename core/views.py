from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
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


def _find_policy(slug: str):
    """Return the LogicalPolicy for `slug`, or None if not found.

    Composes load_working_copy_config + BundleAwarePolicyReader the same
    way `catalog` does. Returns None on any infrastructure issue so the
    caller can choose how to handle it (typically 404).
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return None
    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return None
    for policy in BundleAwarePolicyReader(policies_dir).read():
        if policy.slug == slug:
            return policy
    return None


@login_required
def policy_edit(request, slug):
    """Edit a single non-foundational policy and open a PR.

    Task 3 lands the slug lookup + 404 path. Task 4 adds form rendering,
    Task 5 the foundational gate, Task 6 the POST happy path, Task 7 the
    GitHubProvider failure handling.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    # Temporary placeholder context until Task 4 wires the form. Returns a 200
    # with the scaffold template so the URL-routing tests are not blocked by
    # form code that does not exist yet.
    from core.forms import PolicyEditForm  # local import; Task 4 creates the module
    form = PolicyEditForm(initial={
        "title": policy.frontmatter.get("title", policy.slug),
        "body": policy.body,
        "summary": "",
    })
    return render(request, "policy_edit.html", {"policy": policy, "form": form})
