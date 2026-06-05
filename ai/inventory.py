"""AI-10 inventory-pass orchestrator.

Runs the per-policy extraction across an ingested manifest, emits
policies/<slug>.md + policies/<slug>.audit.yaml drafts into the diocese
working copy, then opens ONE bulk draft PR via the git provider.

Django-free (so it is unit-testable without the Django test harness): the
caller supplies the git provider, the LLM provider, the loaded taxonomy, and
the git author. The thin management command
(core/management/commands/run_inventory_pass.py) does the Django-side wiring.

Re-run safety: a slug whose flat policies/<slug>.md OR bundle dir
policies/<slug>/ already exists is skipped, never overwritten. This protects
human edits and the foundational document-retention bundle.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

# Capabilities the inventory pass needs the diocese's foundational bundle to
# provide for retention/address grounding. Matches spike/extract.py.
REQUIRED_CAPABILITIES = ("classifications", "retention-schedule")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Lowercase ascii slug; non-alphanumerics collapse to single hyphens.

    Falls back to "policy" when the input has no slug-able characters, so a
    target filename always exists.
    """
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or "policy"


def make_inventory_branch_name() -> str:
    """policycodex/inventory-<8-hex>. Deliberately NOT slug-mapped (like the
    onboarding init branch) so the catalog's per-slug gate lookup ignores this
    bulk-import PR."""
    return f"policycodex/inventory-{uuid.uuid4().hex[:8]}"


@dataclass
class InventoryResult:
    """Outcome of one inventory pass.

    written: slugs whose .md + .audit.yaml were written and staged.
    skipped_existing: slugs already present in the working copy (not clobbered).
    skipped_empty: source filenames whose extracted text was blank.
    skipped_unsupported: source filenames with no registered extractor.
    errors: {slug: message} for files whose extraction failed to parse.
    pr: provider open_pr() metadata dict, or None when nothing was written.
    """

    written: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    skipped_empty: list[str] = field(default_factory=list)
    skipped_unsupported: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    pr: dict | None = None
