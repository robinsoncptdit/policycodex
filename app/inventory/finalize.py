"""Open the bulk PR at the end of an inventory pass.

Drafts only (config and retention bundle ship via the Settings panels,
not via this finalize)."""
from __future__ import annotations

import uuid
from pathlib import Path

from app.git_provider.github_provider import GitHubProvider
from app.git_provider.propose import propose_change, working_copy_lock


def finalize_after_inventory(run, *, working_dir: Path) -> None:
    """Push every drafted policy under <working_dir>/policies/ in one PR."""
    drafts_dir = working_dir / "policies"
    if not drafts_dir.exists():
        return

    # Hold the working-copy lock across the glob AND the propose: gunicorn runs
    # multiple workers on one shared copy, so a concurrent save must not remove
    # the drafts (or touch .git) between listing and committing them.
    with working_copy_lock(working_dir):
        drafts = sorted(
            p for p in drafts_dir.iterdir()
            if p.is_file() and p.suffix in {".md", ".yaml"}
        )
        if not drafts:
            return  # Nothing to commit.

        commit_message = (
            f"PolicyCodex inventory pass: {run.completed} drafted, "
            f"{run.failed} failed\n\n"
            f"Co-Authored-By: PolicyCodex <bot@policycodex>"
        )
        branch_name = f"policycodex/inventory-{run.pk}-{uuid.uuid4().hex[:8]}"
        pr = propose_change(
            provider=GitHubProvider(),
            working_dir=working_dir,
            default_branch="main",
            branch_name=branch_name,
            files=drafts,
            commit_message=commit_message,
            author_name="PolicyCodex",
            author_email="bot@policycodex",
            pr_title=f"PolicyCodex inventory pass: {run.completed} drafted",
            pr_body="Drafted policies from the most recent inventory pass.",
        )
    run.pr_url = pr.get("url", "")
    run.save()
