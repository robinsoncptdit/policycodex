import logging
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from core.forms import PolicyEditForm
from core.git_identity import get_git_author
from core.policy_writer import _render_policy_md
from ingest.policy_reader import BundleAwarePolicyReader


logger = logging.getLogger(__name__)


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
