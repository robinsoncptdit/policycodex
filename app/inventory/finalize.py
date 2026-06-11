"""DISC-14: open the single bulk PR at the end of the inventory pass.

Design note: finalize_after_inventory is called from status_fragment (the HTMX
polling endpoint) once the background runner marks the run as "completed". The
caller passes working_dir, config_yaml_text, and bundle_dir explicitly because
status_fragment derives them from (a) the working-copy config (working_dir) and
(b) the wizard session state (config_yaml_text), which are both available since
the same admin browser session that started the run is the one doing the polling.
No migration is needed: all data lives in existing stores.

The drafts_dir is always working_dir/policies — the inventory orchestrator writes
extracted policy drafts there as flat *.md + *.audit.yaml files. The foundational
bundle directory (policies/document-retention) is passed separately as bundle_dir
and is excluded from the flat-file enumeration inside finalize_onboarding.
"""
from __future__ import annotations

from pathlib import Path

from app.git_provider.github_provider import GitHubProvider
from app.onboarding.finalize import finalize_onboarding
from app.working_copy.config import load_working_copy_config


def finalize_after_inventory(
    run,
    *,
    working_dir: Path,
    config_yaml_text: str,
    bundle_dir: Path,
) -> dict:
    """Open one PR containing config + retention bundle + extracted policy drafts.

    Args:
        run: The InventoryRun instance. Its pr_url field is populated on success.
        working_dir: Root of the local working copy (parent of ``policies/``).
        config_yaml_text: Serialized YAML for ``.policycodex/config.yaml``.
        bundle_dir: Path to the foundational retention bundle directory.

    Returns the PR metadata dict from the provider.
    Raises on any git/provider failure (caller records pr_error and re-raises).
    """
    wcc = load_working_copy_config()
    drafts_dir = working_dir / "policies"

    pr = finalize_onboarding(
        working_dir=working_dir,
        config_yaml_text=config_yaml_text,
        bundle_dir=bundle_dir,
        drafts_dir=drafts_dir,
        provider=GitHubProvider(),
        author_name="PolicyCodex",
        author_email="bot@policycodex",
        base_branch=wcc.branch,
        username="onboarding",
    )
    run.pr_url = pr["url"]
    run.save()
    return pr
