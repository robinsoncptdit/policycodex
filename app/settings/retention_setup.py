"""Upload -> extract -> PR for the document-retention foundational bundle.

Wires three existing pieces the 2026-06-11 pivot left disconnected (APP-15):
ingest.extractors.extract (document -> text), ai.retention_extract
(text -> validated data.yaml), and app.git_provider.propose.propose_change
(branch/commit/push/PR). Writes both bundle files and proposes them as one PR
inside working_copy_lock, so the inventory pass (hard-gated on this bundle)
can run. Collaborators are injected so this is unit-testable without an LLM or
network.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from ai.retention_extract import (
    RetentionExtractionError,
    build_data_yaml,
    extract_retention_bundle,
)
from app.git_provider.propose import propose_change, working_copy_lock
from ingest.extractors import extract

RETENTION_SLUG = "document-retention"
RETENTION_PROVIDES = ("classifications", "retention-schedule")


def _render_policy_md(*, title: str, owner: str) -> str:
    """The bundle's policy.md: foundational frontmatter + a short narrative.
    data.yaml carries the machine-readable taxonomy; this file marks the
    directory as the foundational source of truth."""
    provides_lines = "".join(f"- {cap}\n" for cap in RETENTION_PROVIDES)
    return (
        "---\n"
        f"title: {title}\n"
        f"owner: {owner}\n"
        "foundational: true\n"
        "provides:\n"
        f"{provides_lines}"
        "---\n\n"
        f"# {title}\n\n"
        "This foundational policy is the diocese's source of truth for document\n"
        "classifications and the records-retention schedule. The machine-readable\n"
        "data lives in `data.yaml`; edit it through PolicyCodex, not by hand.\n"
    )


def scaffold_retention_bundle(
    *,
    document_path: Path,
    working_dir: Path,
    default_branch: str,
    llm_provider,
    provider,
    author_name: str,
    author_email: str,
    title: str = "Document Retention Policy",
    owner: str = "CFO",
    extract_text=extract,
    extract_bundle=extract_retention_bundle,
    build_yaml=build_data_yaml,
    propose_fn=propose_change,
) -> dict:
    """Parse `document_path` into the document-retention bundle and open a PR.

    Raises RetentionExtractionError if no text can be read or the model output
    is not a valid bundle. Propagates provider/git errors from propose_fn
    (which restores a clean working copy on failure). Returns the PR dict.
    """
    text = extract_text(document_path)
    if not text or not text.strip():
        raise RetentionExtractionError(
            "No text could be extracted from the document (it may be a scanned "
            "image PDF, which v0.1 cannot read)."
        )
    bundle = extract_bundle(llm_provider, text)
    data_yaml_text = build_yaml(bundle)  # validates; raises RetentionExtractionError
    policy_md_text = _render_policy_md(title=title, owner=owner)

    bundle_dir = working_dir / "policies" / RETENTION_SLUG
    policy_md = bundle_dir / "policy.md"
    data_yaml = bundle_dir / "data.yaml"
    branch_name = f"policycodex/foundational-{RETENTION_SLUG}-{uuid.uuid4().hex[:8]}"

    # Write + propose under one lock: a single shared working copy serves all
    # gunicorn workers (see commit 6c35aec).
    with working_copy_lock(working_dir):
        bundle_dir.mkdir(parents=True, exist_ok=True)
        policy_md.write_text(policy_md_text, encoding="utf-8")
        data_yaml.write_text(data_yaml_text, encoding="utf-8")
        return propose_fn(
            provider=provider,
            working_dir=working_dir,
            default_branch=default_branch,
            branch_name=branch_name,
            files=[policy_md, data_yaml],
            commit_message=(
                "Add document-retention foundational bundle\n\n"
                "Co-Authored-By: PolicyCodex <bot@policycodex>"
            ),
            author_name=author_name,
            author_email=author_email,
            pr_title="Add document-retention foundational bundle",
            pr_body=(
                "AI-parsed from the uploaded retention policy by PolicyCodex.\n\n"
                "policies/document-retention/ (policy.md + data.yaml).\n"
                "Review the classifications and retention schedule, then merge to "
                "make the inventory pass available."
            ),
        )
