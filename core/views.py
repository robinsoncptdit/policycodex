import logging
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from github import GithubException

from app.git_provider.github_provider import GitHubProvider
from app.git_provider.states import branch_to_slug
from app.working_copy.config import load_working_copy_config
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
    rows = [
        {"policy": policy, "gate": gate_lookup.get(policy.slug, "published")}
        for policy in policies
    ]
    return render(request, "catalog.html", {"is_empty_onboarding": False, "rows": rows})


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

        try:
            provider.branch(branch_name, working_dir)
            provider.commit(
                message=commit_message,
                files=[policy.policy_path],
                author_name=author_name,
                author_email=author_email,
                working_dir=working_dir,
            )
            provider.push(branch_name, working_dir)
            pr_title = f"Edit policies/{slug}: {commit_message}"
            pr_body = (
                f"Opened by PolicyCodex on behalf of {request.user.username}.\n"
                f"\n"
                f"Policy: policies/{slug}\n"
                f"Author: {author_name} <{author_email}>\n"
            )
            if summary:
                pr_body += f"\n{summary}\n"
            pr = provider.open_pr(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch=config.branch,
                working_dir=working_dir,
            )
        except (RuntimeError, ValueError) as exc:
            logger.error("APP-07 provider failure on slug=%s: %s", slug, exc)
            messages.error(
                request,
                "Couldn't open the pull request. The change is saved locally; "
                "ask your administrator to retry from the server logs.",
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
