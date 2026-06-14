import logging
import uuid
from pathlib import Path

import yaml
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.permissions import require_role
from django.contrib.auth.views import PasswordChangeView
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from github import GithubException

from core.lifecycle import lifecycle_state

from app.git_provider.github_provider import GitHubProvider
from app.git_provider.propose import propose_change
from app.git_provider.states import branch_to_slug
from app.working_copy.config import load_working_copy_config
from app.working_copy.manager import WorkingCopyManager
from ai.retention_extract import RetentionExtractionError, build_data_yaml
from ai.taxonomy_loader import load_foundational_taxonomy
from core.forms import (
    ClassificationForm,
    ClassificationFormSet,
    FoundationalEditMetaForm,
    RetentionRowForm,
    RetentionRowFormSet,
)
from core.forms import PolicyEditForm
from core.git_identity import get_git_author
from core.policy_writer import _render_policy_md
from ingest.policy_reader import BundleAwarePolicyReader


logger = logging.getLogger(__name__)


def health(request):
    return JsonResponse({"status": "ok"})


def _build_gate_lookup(working_dir: Path) -> dict[str, dict]:
    """Call list_open_prs once and return a {slug: {gate, pr}} map.

    Returns an empty dict on any provider failure: the catalog gracefully
    falls back to treating every policy as Published when GitHub is
    unreachable. The PR sub-dict carries number/title/author/html_url so
    the Pending Review section can render per-PR Approve buttons without
    making a second API call.
    """
    try:
        provider = GitHubProvider()
        open_prs = provider.list_open_prs(working_dir)
    except (RuntimeError, GithubException) as exc:
        logger.warning(
            "APP-17 list_open_prs failed (%s); degrading to all-Published", exc
        )
        return {}

    lookup: dict[str, dict] = {}
    for pr in open_prs:
        slug = branch_to_slug(pr.get("head_branch", ""))
        if slug is None:
            continue
        existing = lookup.get(slug, {}).get("gate")
        if existing == "reviewed":
            continue
        lookup[slug] = {
            "gate": pr.get("gate", "drafted"),
            "pr": {
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "author": pr.get("author", ""),
                "html_url": pr.get("html_url", ""),
            },
        }
    return lookup


@require_role("Viewer")
def catalog(request):
    """Render the policy inventory from the local working copy.

    Falls back to an empty-state template when the working copy is not
    yet configured (fresh install before it is configured) or not yet synced.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return render(request, "catalog.html", {
            "is_unconfigured": True,
            "rows": [],
            "last_sync": None,
        })

    import json as _json
    last_sync = None
    marker = config.working_dir / ".policycodex" / "last_sync.json"
    if marker.exists():
        try:
            last_sync = _json.loads(marker.read_text()).get("iso")
        except (OSError, ValueError):
            last_sync = None

    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return render(request, "catalog.html", {
            "is_unconfigured": True,
            "rows": [],
            "last_sync": last_sync,
        })

    from core.services import build_catalog
    catalog_data = build_catalog(
        policies_dir,
        config.working_dir,
        reader_cls=BundleAwarePolicyReader,
        load_taxonomy=load_foundational_taxonomy,
        gate_lookup_fn=_build_gate_lookup,
    )
    return render(
        request,
        "catalog.html",
        {
            "is_unconfigured": False,
            "rows": catalog_data["rows"],
            "gap_count": catalog_data["gap_count"],
            "pending_review": catalog_data["pending_review"],
            "last_sync": last_sync,
        },
    )


def root_redirect(request):
    """Route the root URL to /catalog/.

    A seeded admin exists from first install (Task 3 of the Settings-page
    rebuild). Unauthenticated visitors reach /catalog/ which @login_required
    bounces to /login/ normally.
    """
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


@require_role("Viewer")
def policy_detail(request, slug):
    """Read-only detail view for a single policy (APP-23).

    Renders the title, frontmatter, provides:, body, and gate state. Applies
    the same L1 foundational gate as the catalog: foundational policies show
    the typed-table-editor banner and no flat-edit affordance; non-foundational
    policies show an Edit link. This view never mutates.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")

    # Reuse the catalog's gate lookup so the detail badge matches the list
    # badge exactly. Degrades to "published" on any provider/config failure.
    try:
        config = load_working_copy_config()
        gate = _build_gate_lookup(config.working_dir).get(slug, {"gate": "published"})["gate"]
    except RuntimeError:
        gate = "published"

    return render(request, "policy_detail.html", {"policy": policy, "gate": gate})


def _make_branch_name(slug: str) -> str:
    """policycodex/edit-<slug>-<short-uuid>. See plan rationale."""
    return f"policycodex/edit-{slug}-{uuid.uuid4().hex[:8]}"


@require_role("Editor")
def policy_edit(request, slug):
    """GET pre-populates an edit form; POST writes the file, branches,
    commits authored by the user, pushes, and opens a PR back to the
    diocese's policy repo.

    Foundational policies edit through the typed-table UI (APP-20),
    never this form: GET and POST both return 403.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    if policy.foundational:
        return render(
            request,
            "foundational_edit_forbidden.html",
            {"policy": policy},
            status=403,
        )

    if request.method == "POST":
        form = PolicyEditForm(request.POST)
        if not form.is_valid():
            return render(request, "policy_edit.html", {"policy": policy, "form": form})

        config = load_working_copy_config()
        from core.services import propose_policy_edit
        try:
            pr = propose_policy_edit(
                policy, slug,
                user=request.user,
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                summary=form.cleaned_data.get("summary"),
                config=config,
                provider=GitHubProvider(),
                branch_name=_make_branch_name(slug),
                render_md=_render_policy_md,
                git_author_fn=get_git_author,
                propose_fn=propose_change,
            )
        except Exception as exc:
            logger.error("APP-07 propose_change failure on slug=%s: %s", slug, exc)
            messages.error(
                request,
                "Couldn't open the pull request. Please try again.",
            )
            return render(
                request,
                "policy_edit.html",
                {"policy": policy, "form": form},
            )

        return render(
            request,
            "policy_edit_success.html",
            {"policy": policy, "pr": pr},
        )

    form = PolicyEditForm(initial={
        "title": policy.frontmatter.get("title", policy.slug),
        "body": policy.body,
        "summary": "",
    })
    return render(request, "policy_edit.html", {"policy": policy, "form": form})


def _classification_initial(data: dict) -> list[dict]:
    return [
        {"id": c.get("id", ""), "name": c.get("name", ""), "deprecated": bool(c.get("deprecated", False))}
        for c in (data.get("classifications") or [])
    ]


def _retention_initial(data: dict) -> list[dict]:
    rows = []
    for r in (data.get("retention_schedule") or []):
        rows.append({
            "group": r.get("group", ""),
            "sub_group": r.get("sub_group", ""),
            "type": r.get("type", ""),
            "retention": r.get("retention", ""),
            "medium": r.get("medium", ""),
            "retained_at": r.get("retained_at", ""),
        })
    return rows


@require_role("Editor")
def foundational_edit(request, slug):
    """Typed-table editor for a foundational bundle's data.yaml (APP-25).

    GET renders editable classification + retention-row tables prefilled
    from data.yaml. POST writes an edited data.yaml and opens a PR through
    the same gate flow as policy_edit. Non-foundational policies are sent to
    the flat editor; this view edits only foundational bundles.
    """
    policy = _find_policy(slug)
    if policy is None:
        raise Http404(f"Policy not found: {slug}")
    if not policy.foundational:
        return redirect("policy_edit", slug=slug)

    data = yaml.safe_load(policy.data_path.read_text(encoding="utf-8")) or {}

    if request.method == "POST":
        return _foundational_edit_post(request, slug, policy)

    cforms = ClassificationFormSet(
        initial=_classification_initial(data), prefix="cls"
    )
    rforms = RetentionRowFormSet(
        initial=_retention_initial(data), prefix="ret"
    )
    meta = FoundationalEditMetaForm()
    return render(request, "foundational_edit.html", {
        "policy": policy, "cforms": cforms, "rforms": rforms, "meta": meta,
    })


def _foundational_edit_post(request, slug, policy):
    cforms = ClassificationFormSet(request.POST, prefix="cls")
    rforms = RetentionRowFormSet(request.POST, prefix="ret")
    meta = FoundationalEditMetaForm(request.POST)

    def _render(error=None):
        return render(request, "foundational_edit.html", {
            "policy": policy, "cforms": cforms, "rforms": rforms,
            "meta": meta, "error": error,
        })

    if not (cforms.is_valid() and rforms.is_valid() and meta.is_valid()):
        return _render()

    from core.services import build_foundational_bundle, propose_foundational_edit
    bundle = build_foundational_bundle(cforms, rforms)
    config = load_working_copy_config()
    try:
        pr = propose_foundational_edit(
            policy, slug, bundle=bundle, summary=meta.cleaned_data.get("summary"),
            user=request.user, config=config, provider=GitHubProvider(),
            branch_name=_make_branch_name(slug), build_yaml_fn=build_data_yaml,
            git_author_fn=get_git_author, propose_fn=propose_change,
        )
    except RetentionExtractionError as exc:
        return _render(error=f"Could not save: {exc}")
    except Exception as exc:
        logger.error("APP-25 propose_change failure on slug=%s: %s", slug, exc)
        # Surface the failure inline (not via messages.error like policy_edit):
        # foundational_edit.html has no messages block, and inline keeps the
        # admin's unsaved table edits on screen instead of a bare redirect.
        return _render(
            error="Couldn't open the pull request. Please try again."
        )

    return render(request, "policy_edit_success.html", {"policy": policy, "pr": pr})


@login_required
@require_POST
def foundational_row(request, slug):
    """APP-28c: return one fresh typed-table row plus an out-of-band bump of
    the formset's TOTAL_FORMS, so HTMX can append a row without a reload and
    the Django formset accepts it on POST. `slug` scopes the request to a
    bundle but the row markup is bundle-independent."""
    which = request.POST.get("formset")
    try:
        index = int(request.POST.get("index", "0"))
    except (TypeError, ValueError):
        index = 0
    if which == "ret":
        form = RetentionRowForm(prefix=f"ret-{index}")
        template = "fragments/retention_row.html"
        prefix = "ret"
    else:
        form = ClassificationForm(prefix=f"cls-{index}")
        template = "fragments/classification_row.html"
        prefix = "cls"
    return render(request, template, {
        "form": form, "prefix": prefix, "index": index, "next_total": index + 1,
    })


@require_role("Editor")
@require_POST
def approve_pr(request):
    """Approve an open PR on behalf of the authenticated reviewer.

    The Django user who clicked the button is logged for the app's audit
    trail. The GitHub-side actor on the review is the App installation
    identity, per the v0.1 ticket scope.

    v0.1 permission model: any authenticated Django user may approve.
    Future tickets (reviewer-role gating) will add per-user authorization.

    Gate-guard: only `drafted`-state PRs are approvable. Approving an
    already-reviewed, merged, or closed PR is refused with a flash error.
    The check is at the view layer (not the provider) because v0.1 is a
    single-server single-process app; concurrent-approval races are not
    a real risk at our scale, and surfacing the state in the flash message
    is more useful to the user than a provider-layer raise.
    """
    raw = request.POST.get("pr_number", "").strip()
    if not raw:
        messages.error(request, "Missing pr_number.")
        return redirect("catalog")
    try:
        pr_number = int(raw)
    except ValueError:
        messages.error(request, f"Invalid pr_number: {raw!r}.")
        return redirect("catalog")
    if pr_number < 1:
        messages.error(request, f"PR number must be positive (got {pr_number}).")
        return redirect("catalog")

    try:
        config = load_working_copy_config()
    except RuntimeError as exc:
        messages.error(request, f"Working copy not configured: {exc}")
        return redirect("catalog")

    provider = GitHubProvider()
    try:
        state = provider.read_pr_state(pr_number, config.working_dir)
    except Exception as exc:
        messages.error(request, f"Could not read PR #{pr_number} state: {exc}")
        logger.warning(
            "approve_pr: read_pr_state failed user=%s pr=%s err=%s",
            request.user.username, pr_number, exc,
        )
        return redirect("catalog")

    if state != "drafted":
        logger.warning(
            "approve_pr: PR %s in state %s, not drafted; user=%s",
            pr_number, state, request.user.username,
        )
        messages.error(
            request,
            f"PR #{pr_number} is in state '{state}', not 'drafted'. Refresh the catalog or check the PR on GitHub.",
        )
        return redirect("catalog")

    try:
        result = provider.approve_pr(
            pr_number=pr_number,
            working_dir=config.working_dir,
            body="",
        )
    except Exception as exc:
        messages.error(request, f"Could not approve PR #{pr_number}: {exc}")
        logger.warning(
            "approve_pr: provider error user=%s pr=%s err=%s",
            request.user.username, pr_number, exc,
        )
        return redirect("catalog")

    logger.info(
        "approve_pr: success user=%s pr=%s review_id=%s",
        request.user.username, pr_number, result.get("review_id"),
    )
    messages.success(request, f"PR #{pr_number} approved.")
    return redirect("catalog")


@require_role("Editor")
@require_http_methods(["POST"])
def publish_policy(request, slug):
    """Merge the open PR for `slug`, transitioning the gate to Published.

    v0.1 permission model: any authenticated user may publish. Role-gating
    (e.g. "only Publisher role") is a future ticket. The GitHub App token
    used by GitHubProvider has Contents + Pull-requests read/write
    (verified in REPO-03 checklist), which is the underlying authority.

    All outcomes (success or any error class) flash a message via Django's
    messages framework and redirect to /catalog/. No JSON, no rendered
    error page, no 500.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        messages.error(
            request,
            "Working copy is not configured. Configure the policy repository in Settings first.",
        )
        return redirect("catalog")

    working_dir = config.working_dir
    provider = GitHubProvider()

    # Locate the open PR for this slug by scanning open PRs and matching
    # the head-branch convention (same lookup APP-17's _build_gate_lookup
    # uses for the catalog gate badges). No persistent slug->PR mapping
    # in v0.1; the GitHub API is the source of truth.
    try:
        open_prs = provider.list_open_prs(working_dir)
    except (RuntimeError, GithubException) as exc:
        messages.error(request, f"Could not list open pull requests: {exc}")
        return redirect("catalog")

    matching = [
        pr for pr in open_prs
        if branch_to_slug(pr.get("head_branch", "")) == slug
    ]
    if not matching:
        messages.error(
            request,
            f"No pending pull request for '{slug}'. Open an edit first to create one.",
        )
        return redirect("catalog")
    pr_number = matching[0]["pr_number"]

    try:
        state = provider.read_pr_state(pr_number, working_dir)
    except (RuntimeError, GithubException) as exc:
        messages.error(request, f"Could not read PR state for #{pr_number}: {exc}")
        return redirect("catalog")

    if state == "published":
        messages.warning(request, f"PR #{pr_number} is already published.")
        return redirect("catalog")
    if state != "reviewed":
        messages.error(
            request,
            f"PR #{pr_number} is in state '{state}'. A reviewer must approve "
            "(transition to Reviewed) before it can be published.",
        )
        return redirect("catalog")

    try:
        result = provider.merge_pr(pr_number, working_dir, merge_method="squash")
    except RuntimeError as exc:
        messages.error(
            request,
            f"Merge failed for PR #{pr_number}: {exc}. Resolve the issue on "
            "GitHub (often a merge conflict or branch protection) and try again.",
        )
        return redirect("catalog")

    logger.info(
        "publish_policy: success user=%s slug=%s pr=%s sha=%s",
        request.user.username, slug, pr_number, result.get("sha"),
    )
    messages.success(
        request,
        f"Published '{slug}' (PR #{pr_number} merged as {result['sha'][:7]}).",
    )
    return redirect("catalog")


class ForcedPasswordChangeView(PasswordChangeView):
    # Namespace under core/ so django.contrib.admin's same-named template
    # does not shadow ours via the APP_DIRS loader.
    template_name = "core/password_change_form.html"

    def get_success_url(self):
        profile = self.request.user.profile
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        return lifecycle_state(self.request).next_url


@require_role("Editor")
@require_POST
def catalog_sync(request):
    try:
        config = load_working_copy_config()
        WorkingCopyManager(config, GitHubProvider()).sync()
        # Write last-sync marker so the catalog can render the timestamp.
        from datetime import datetime, timezone
        marker_dir = config.working_dir / ".policycodex"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "last_sync.json").write_text(
            f'{{"iso": "{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}"}}'
        )
        messages.success(request, "Catalog synced from GitHub.")
    except Exception as exc:  # noqa: BLE001 — surfaced to user; provider redacts tokens
        logger.warning("catalog_sync failed user=%s err=%s", request.user.username, exc)
        messages.error(request, f"Could not sync: {exc}")
    return redirect("catalog")
