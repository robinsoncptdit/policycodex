"""DISC-14: open the single bulk PR at the end of the inventory pass.

Design note: finalize_after_inventory is called from status_fragment (the HTMX
polling endpoint) once the background runner marks the run as "completed". The
caller passes working_dir explicitly because status_fragment derives it from
the working-copy config (working_dir), which is available since the same admin
browser session that started the run is the one doing the polling.
No migration is needed: all data lives in existing stores.

The drafts_dir is always working_dir/policies — the inventory orchestrator writes
extracted policy drafts there as flat *.md + *.audit.yaml files. The foundational
bundle directory (policies/document-retention) is passed separately as bundle_dir
and is excluded from the flat-file enumeration inside finalize_onboarding.

Note (Task 28): finalize_after_inventory will be simplified to (run, *, working_dir)
once the Settings-page rebuild delivers the Policy Repository panel. The
config_yaml_text and bundle_dir kwargs are legacy from the pre-pivot flow and
will be dropped in Phase 5 Task 28.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.git_provider.github_provider import GitHubProvider
from app.git_provider.propose import propose_change
from app.working_copy.config import load_working_copy_config

# ---------------------------------------------------------------------------
# Helpers relocated from the deleted onboarding module (Phase 1 tear-down).
# Task 28 will simplify the whole finalize path; these helpers keep tests
# green in the interim.
# ---------------------------------------------------------------------------

CONFIG_SCHEMA_VERSION = 1
CONFIG_DIR_NAME = ".policycodex"
CONFIG_FILE_NAME = "config.yaml"

_SECRET_KEY_MARKERS = (
    "token", "secret", "password", "api_key", "apikey", "credential",
)


def _is_secret_key(key: str) -> bool:
    low = str(key).lower()
    return any(marker in low for marker in _SECRET_KEY_MARKERS)


def write_config_file(working_dir: Path, config_yaml_text: str) -> Path:
    """Write `.policycodex/config.yaml` under the working copy. Returns its path."""
    config_dir = Path(working_dir) / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_FILE_NAME
    text = config_yaml_text if config_yaml_text.endswith("\n") else config_yaml_text + "\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def make_onboarding_branch_name() -> str:
    """policycodex/onboarding-<short-uuid>."""
    return f"policycodex/onboarding-{uuid.uuid4().hex[:8]}"


def _collect_draft_files(drafts_dir: Path) -> list[Path]:
    """Return *.md and *.audit.yaml files directly under drafts_dir.

    Only top-level files are collected; foundational bundle directories
    (which are directories, not flat files) are excluded because the
    bundle_dir argument already covers the retention bundle.
    """
    files: list[Path] = []
    for p in sorted(drafts_dir.iterdir()):
        if p.is_file() and (p.suffix == ".md" or p.name.endswith(".audit.yaml")):
            files.append(p)
    return files


def finalize_onboarding(
    *,
    working_dir: Path,
    config_yaml_text: str,
    bundle_dir: Path,
    provider,
    author_name: str,
    author_email: str,
    base_branch: str,
    username: str,
    drafts_dir: Path | None = None,
) -> dict:
    """Write the config file, then funnel through propose_change.

    Commits config_path + bundle_dir; when drafts_dir is provided, also
    commits all *.md and *.audit.yaml files found directly under it (the
    extracted policy drafts from the inventory pass). Never `git add .`.
    Returns the PR metadata dict. On any failure, propose_change restores a
    clean default branch and re-raises; the caller is responsible for the
    user-facing degrade. On success the working copy is left back on the
    default branch.
    """
    config_path = write_config_file(working_dir, config_yaml_text)
    branch_name = make_onboarding_branch_name()
    message = "Initialize diocese configuration and document-retention policy"

    files: list[Path] = [config_path, bundle_dir]
    draft_files: list[Path] = []
    if drafts_dir is not None and drafts_dir.is_dir():
        draft_files = _collect_draft_files(drafts_dir)
        files.extend(draft_files)

    drafted_section = ""
    if draft_files:
        policy_lines = "\n".join(
            f"  - policies/{f.name}" for f in draft_files if f.suffix == ".md"
        )
        drafted_section = (
            f"\nDrafted policies ({len([f for f in draft_files if f.suffix == '.md'])}):\n"
            f"{policy_lines}\n"
        )

    pr_body = (
        f"Opened by PolicyCodex during setup on behalf of {username}.\n\n"
        f"Contents:\n"
        f"- {CONFIG_DIR_NAME}/{CONFIG_FILE_NAME} (diocese configuration)\n"
        f"- policies/{bundle_dir.name}/ (document-retention foundational policy)\n"
        f"{drafted_section}"
    )
    return propose_change(
        provider=provider,
        working_dir=Path(working_dir),
        default_branch=base_branch,
        branch_name=branch_name,
        files=files,
        commit_message=message,
        author_name=author_name,
        author_email=author_email,
        pr_title="Initialize policy repository",
        pr_body=pr_body,
    )


# ---------------------------------------------------------------------------
# Public API: called from status_fragment on run completion.
# ---------------------------------------------------------------------------

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
        username="setup",
    )
    run.pr_url = pr["url"]
    run.save()
    return pr
