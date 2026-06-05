"""Scaffold the diocese's first foundational-policy bundle (APP-15).

Writes policies/document-retention/{policy.md, data.yaml, source.pdf} into
the local working copy. Committing the bundle to the policy repo is APP-16.
The on-disk shape is the contract enforced by ingest.policy_reader.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

BUNDLE_SLUG = "document-retention"
PROVIDES = ["classifications", "retention-schedule"]


def scaffold_retention_bundle(
    policies_dir: Path,
    *,
    title: str,
    owner: str,
    narrative: str,
    data_yaml_text: str,
    source_pdf: Path | None,
) -> Path:
    """Create the document-retention bundle under `policies_dir`. Returns its dir.

    Idempotent on the directory; re-running overwrites an existing bundle's
    files in place (onboarding writes once into a fresh working copy).
    """
    bundle_dir = Path(policies_dir) / BUNDLE_SLUG
    bundle_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = yaml.safe_dump(
        {"title": title, "owner": owner, "foundational": True, "provides": PROVIDES},
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    body = narrative if narrative.endswith("\n") else narrative + "\n"
    (bundle_dir / "policy.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")

    text = data_yaml_text if data_yaml_text.endswith("\n") else data_yaml_text + "\n"
    (bundle_dir / "data.yaml").write_text(text, encoding="utf-8")

    if source_pdf is not None:
        shutil.copyfile(source_pdf, bundle_dir / "source.pdf")

    return bundle_dir
