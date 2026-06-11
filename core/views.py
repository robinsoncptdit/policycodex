import logging
import uuid
from pathlib import Path

import yaml
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from ai.gap_detection import is_gap, known_types
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


def _build_gate_lookup(working_dir: Path) -> dict[str, str]:
    """Call list_open_prs once and return a {slug: gate} map.

    Returns an empty dict on any provider failure: the catalog gracefully
    falls back to treating every policy as Published when GitHub is
    unreachable. Logging the failure is a follow-up; v0.1 prioritizes the
    page rendering over surfacing the network error.
    """
    try:
        provider = GitHubProvider()
        open_prs = provider.list_open_prs(working_dir)
    except (RuntimeError, GithubException) as exc:
        logger.warning(
            "APP-17 list_open_prs failed (%s); degrading to all-Published", exc
        )
        return {}

    lookup: dict[str, str] = {}
    for pr in open_prs:
        slug = branch_to_slug(pr.get("head_branch", ""))
        if slug is None:
            continue
        # If two PRs target the same slug (shouldn't happen with branch
        # protection, but defensive), keep the more-advanced gate.
        existing = lookup.get(slug)
        if existing == "reviewed":
            continue
        lookup[slug] = pr.get("gate", "drafted")
    return lookup


@login_required
def catalog(request):
    """Render the policy inventory from the local working copy.

    Falls back to an empty-state template when the working copy is not
    yet configured (fresh install before onboarding) or not yet synced.
    """
    try:
        config = load_working_copy_config()
    except RuntimeError:
        return render(request, "catalog.html", {"is_empty_onboarding": True, "rows": []})

    policies_dir: Path = config.working_dir / "policies"
    if not policies_dir.exists():
        return render(request, "catalog.html", {"is_empty_onboarding": True, "rows": []})

    policies = list(BundleAwarePolicyReader(policies_dir).read())
    gate_lookup = _build_gate_lookup(config.working_dir)

    # AI-13: flag policies whose type is not in the diocese's retention
    # bundle classifications. Load via the same taxonomy loader the AI
    # extraction uses, so both see identical types. Any load failure (no
    # bundle, malformed data.yaml) degrades to no gap detection rather than
    # 500-ing the catalog; gap flags only appear when classifications exist.
    try:
        taxonomy = load_foundational_taxonomy(policies_dir, ["classifications"])
    except Exception as exc:  # noqa: BLE001 - catalog must always render
        logger.warning("AI-13 taxonomy load failed (%s); gap detection off", exc)
        taxonomy = None
    known = known_types((taxonomy or {}).get("classifications"))

    rows = []
    gap_count = 0
    for policy in policies:
        gap = bool(known) and is_gap(policy.frontmatter.get("category"), known)
        if gap:
            gap_count += 1
        rows.append({
            "policy": policy,
            "gate": gate_lookup.get(policy.slug, "published"),
            "is_gap": gap,
        })

    return render(
        request,
        "catalog.html",
        {"is_empty_onboarding": False, "rows": rows, "gap_count": gap_count},
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


@login_required
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
        gate = _build_gate_lookup(config.working_dir).get(slug, "published")
    except RuntimeError:
        gate = "published"

    return render(request, "policy_detail.html", {"policy": policy, "gate": gate})


def _make_branch_name(slug: str) -> str:
    """policycodex/edit-<slug>-<short-uuid>. See plan rationale."""
    return f"policycodex/edit-{slug}-{uuid.uuid4().hex[:8]}"


@login_required
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

        # 1. Merge form values into the policy's existing frontmatter
        #    (preserves all keys the form does not expose).
        #
        # v0.1 assumes a single editor at a time; we do NOT re-read the
        # file from disk inside this block. A pull from `manage.py
        # pull_working_copy` running concurrently between _find_policy()
        # above and the write_text() below could in principle overwrite a
        # newer revision. Single-server, single-admin deployments make
        # this race vanishingly rare; future tickets can add a stat-based
        # mtime check or an in-memory lock if real dioceses see thrash.
        new_fm = dict(policy.frontmatter)
        new_fm["title"] = form.cleaned_data["title"]
        new_body = form.cleaned_data["body"]
        new_text = _render_policy_md(new_fm, new_body)

        # 2. Write the file in the local working copy.
        policy.policy_path.write_text(new_text, encoding="utf-8")

        # 3. Sequence the four GitHub operations.
        config = load_working_copy_config()
        working_dir = config.working_dir
        provider = GitHubProvider()
        author_name, author_email = get_git_author(request.user)
        branch_name = _make_branch_name(slug)
        summary = (form.cleaned_data.get("summary") or "").strip()
        commit_message = summary or f"Update {slug}"

        pr_title = f"Edit policies/{slug}: {commit_message}"
        pr_body = (
            f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
            f"\n"
            f"Policy: policies/{slug}\n"
            f"Author: {author_name} <{author_email}>\n"
        )
        if summary:
            pr_body += f"\n{summary}\n"

        # propose_change runs branch -> commit -> push -> open_pr; on ANY
        # failure it restores a clean default branch (reverts the write_text
        # above, deletes the local feature branch) so the next sync() pull
        # never wedges on a dirty tree. On success it leaves the working copy
        # back on the default branch (APP-33).
        try:
            pr = propose_change(
                provider=provider,
                working_dir=working_dir,
                default_branch=config.branch,
                branch_name=branch_name,
                files=[policy.policy_path],
                commit_message=commit_message,
                author_name=author_name,
                author_email=author_email,
                pr_title=pr_title,
                pr_body=pr_body,
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


@login_required
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

    initial_count = cforms.initial_form_count()
    classifications = []
    for i, f in enumerate(cforms):
        if not f.cleaned_data:
            continue
        is_existing = i < initial_count
        deleted = f.cleaned_data.get("DELETE")
        if deleted and not is_existing:
            continue
        row = {"id": f.cleaned_data["id"], "name": f.cleaned_data["name"]}
        if deleted or f.cleaned_data.get("deprecated"):
            row["deprecated"] = True
        classifications.append(row)
    retention_schedule = [
        {
            "group": f.cleaned_data["group"],
            "sub_group": f.cleaned_data.get("sub_group", ""),
            "type": f.cleaned_data["type"],
            "retention": f.cleaned_data["retention"],
            "medium": f.cleaned_data.get("medium", ""),
            "retained_at": f.cleaned_data.get("retained_at", ""),
        }
        for f in rforms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]
    bundle = {"classifications": classifications, "retention_schedule": retention_schedule}

    # build_data_yaml validates required fields + drops blank optionals (DRY
    # with the APP-15 bootstrap emitter). Belt-and-suspenders: the formsets
    # already enforce the required fields, so this rarely raises; it guards
    # against a future emitter constraint the form layer doesn't mirror.
    try:
        data_yaml_text = build_data_yaml(bundle)
    except RetentionExtractionError as exc:
        return _render(error=f"Could not save: {exc}")

    # Write the edited data.yaml in the working copy.
    policy.data_path.write_text(data_yaml_text, encoding="utf-8")

    # Same four-operation gate sequence as policy_edit, committing data.yaml.
    config = load_working_copy_config()
    working_dir = config.working_dir
    provider = GitHubProvider()
    author_name, author_email = get_git_author(request.user)
    branch_name = _make_branch_name(slug)
    summary = (meta.cleaned_data.get("summary") or "").strip()
    commit_message = summary or f"Update {slug} classifications and retention schedule"

    pr_title = f"Edit policies/{slug}: {commit_message}"
    pr_body = (
        f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
        f"\n"
        f"Foundational policy: policies/{slug} (data.yaml)\n"
        f"Author: {author_name} <{author_email}>\n"
    )
    if summary:
        pr_body += f"\n{summary}\n"

    # propose_change runs branch -> commit -> push -> open_pr; on ANY
    # failure it restores a clean default branch (reverts the data.yaml
    # write above, deletes the local feature branch). On success it
    # leaves the working copy back on the default branch (APP-33).
    try:
        pr = propose_change(
            provider=provider,
            working_dir=working_dir,
            default_branch=config.branch,
            branch_name=branch_name,
            files=[policy.data_path],
            commit_message=commit_message,
            author_name=author_name,
            author_email=author_email,
            pr_title=pr_title,
            pr_body=pr_body,
        )
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


@login_required
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
        messages.error(
            request,
            f"PR #{pr_number} cannot be approved (current state: {state}).",
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


@login_required
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
    template_name = "registration/password_change_form.html"

    def get_success_url(self):
        profile = self.request.user.profile
        if profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        return lifecycle_state(self.request).next_url
