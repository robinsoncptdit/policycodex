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
human edits and the foundational document-retention bundle. Two source files
that slugify to the same name within one pass are also non-destructive: the
first wins, the rest are reported as collisions rather than clobbering it.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ai import audit, emit
from ai.inventory_extract import InventoryExtractionError, extract_policy_metadata
from ai.provider import LLMProvider
from ingest.extractors import UnsupportedFormatError, extract
from ingest.manifest import ManifestEntry

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
    skipped_changed: slugs whose source content changed since the prior inventory
        (AI-17); the existing draft was preserved (re-extraction would trample
        the maintainer's edits) and the source needs manual review.
    skipped_collision: source filenames that slugify to a slug already drafted
        earlier in THIS pass (a real document, dropped to avoid clobbering its
        sibling; rename the source to disambiguate).
    skipped_empty: source filenames whose extracted text was blank.
    skipped_unsupported: source filenames with no registered extractor.
    errors: {slug: message} for files whose extraction or text read failed.
    pr: provider open_pr() metadata dict, or None when nothing was written.
    """

    written: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    skipped_changed: list[str] = field(default_factory=list)
    skipped_collision: list[str] = field(default_factory=list)
    skipped_empty: list[str] = field(default_factory=list)
    skipped_unsupported: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    pr: dict | None = None


def _build_pr_body(result: "InventoryResult", username: str) -> str:
    lines = [
        f"Opened by PolicyCodex inventory pass on behalf of {username}.",
        "",
        f"Drafted {len(result.written)} policies:",
    ]
    lines += [f"- policies/{slug}.md" for slug in result.written]
    if result.skipped_changed:
        lines += [
            "",
            f"Skipped {len(result.skipped_changed)} source files changed since last inventory "
            "(existing drafts preserved, review manually):",
        ]
        lines += [f"- {slug}" for slug in result.skipped_changed]
    if result.skipped_existing:
        lines += ["", f"Skipped {len(result.skipped_existing)} already present:"]
        lines += [f"- {slug}" for slug in result.skipped_existing]
    if result.skipped_collision:
        lines += ["", f"Skipped {len(result.skipped_collision)} slug collisions (rename to include):"]
        lines += [f"- {name}" for name in result.skipped_collision]
    if result.skipped_empty:
        lines += ["", f"Skipped {len(result.skipped_empty)} with no extractable text:"]
        lines += [f"- {name}" for name in result.skipped_empty]
    if result.skipped_unsupported:
        lines += ["", f"Skipped {len(result.skipped_unsupported)} unsupported formats:"]
        lines += [f"- {name}" for name in result.skipped_unsupported]
    if result.errors:
        lines += ["", f"{len(result.errors)} extraction errors (not committed):"]
        lines += [f"- {slug}: {msg}" for slug, msg in result.errors.items()]
    return "\n".join(lines) + "\n"


def _git(args: list[str], working_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=working_dir, capture_output=True)


def _restore_default_branch(
    working_dir: Path, default_branch: str, written_paths: list[Path], branch_name: str
) -> None:
    """Best-effort: return the working copy to default_branch with a clean tree
    and drop the local feature branch. Never raises (recovery must not mask the
    original error). Mirrors app/git_provider/propose.py's hygiene, duplicated
    here so ai/ stays Django-free and does not import the app layer."""
    _git(["checkout", default_branch], working_dir)
    for p in written_paths:
        p = Path(p)
        tracked = _git(["ls-files", "--error-unmatch", str(p)], working_dir).returncode == 0
        if tracked:
            _git(["checkout", "--", str(p)], working_dir)
        elif p.exists():
            p.unlink(missing_ok=True)
    _git(["branch", "-D", branch_name], working_dir)


def run_inventory_pass(
    *,
    manifest: list[ManifestEntry],
    working_dir: Path,
    provider,
    llm_provider: LLMProvider,
    taxonomy: dict[str, Any] | None,
    author_name: str,
    author_email: str,
    base_branch: str,
    changed_entries: Sequence[ManifestEntry] = (),
    username: str = "PolicyCodex",
    on_item_done=lambda **_: None,
    on_item_failed=lambda **_: None,
) -> InventoryResult:
    """Extract every manifest file, emit drafts, and open one bulk PR.

    For each entry: extract text, run metadata extraction, emit
    policies/<slug>.md + policies/<slug>.audit.yaml into the working copy.
    Slugs already present are skipped (never clobbered). When at least one
    draft is written, branch -> commit (all files) -> push -> open one PR.
    When nothing is written, no branch/commit/PR happens and result.pr is None.

    `provider` is a GitProvider; only branch/commit/push/open_pr are used.
    Any git-provider exception propagates to the caller (the command degrades).
    """
    working_dir = Path(working_dir)
    policies_dir = working_dir / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)

    result = InventoryResult()
    to_commit: list[Path] = []
    written_slugs: set[str] = set()

    # AI-17: surface sources whose content changed since the prior inventory.
    # No LLM call, no file write -- the locked design protects the existing
    # draft (which may carry maintainer edits) from auto-overwrite. The
    # maintainer reviews the source diff and decides what to carry forward.
    for entry in changed_entries:
        result.skipped_changed.append(_slugify(entry.path.stem))

    for entry in manifest:
        slug = _slugify(entry.path.stem)
        md_path = policies_dir / f"{slug}.md"
        audit_path = policies_dir / f"{slug}.audit.yaml"
        bundle_dir = policies_dir / slug

        # Two source files in one pass can slugify to the same name. Treat that
        # as a distinct, surfaced outcome rather than a silent "already present"
        # skip, so a real document is never quietly dropped.
        if slug in written_slugs:
            result.skipped_collision.append(entry.path.name)
            continue
        if md_path.exists() or bundle_dir.is_dir():
            result.skipped_existing.append(slug)
            continue

        try:
            text = extract(entry.path)
        except UnsupportedFormatError:
            result.skipped_unsupported.append(entry.path.name)
            continue
        except Exception as exc:  # noqa: BLE001
            # extract() reads untrusted external document files; one corrupt
            # file must not sink a bulk pass over dozens of others.
            result.errors[slug] = f"read failed: {exc}"
            on_item_failed(source=entry.path.name, error=f"read failed: {exc}")
            continue
        if not text.strip():
            result.skipped_empty.append(entry.path.name)
            continue

        try:
            metadata = extract_policy_metadata(llm_provider, text, taxonomy)
        except InventoryExtractionError as exc:
            result.errors[slug] = str(exc)
            on_item_failed(source=entry.path.name, error=str(exc))
            continue

        metadata["_source_file"] = entry.path.name
        md_path.write_text(emit.to_markdown(metadata), encoding="utf-8")
        audit_path.write_text(audit.to_audit_yaml(metadata), encoding="utf-8")
        to_commit.extend([md_path, audit_path])
        result.written.append(slug)
        written_slugs.add(slug)
        _confidence_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        on_item_done(
            source=entry.path.name,
            slug=slug,
            title=metadata.get("title", ""),
            classification=metadata.get("category", ""),
            confidence=_confidence_map.get(metadata.get("category_confidence", ""), 0.0),
        )

    if not to_commit:
        return result

    branch_name = make_inventory_branch_name()
    message = f"Inventory pass: add {len(result.written)} draft policies"
    try:
        provider.branch(branch_name, working_dir)
        provider.commit(
            message=message,
            files=to_commit,
            author_name=author_name,
            author_email=author_email,
            working_dir=working_dir,
        )
        provider.push(branch_name, working_dir)
        result.pr = provider.open_pr(
            title=f"Inventory pass: {len(result.written)} draft policies",
            body=_build_pr_body(result, username),
            head_branch=branch_name,
            base_branch=base_branch,
            working_dir=working_dir,
        )
    except Exception:
        # APP-33 contract: a provider failure must never strand the working
        # copy on the feature branch. Restore the default branch, then re-raise
        # so the caller records the failure (the prior manifest stays intact).
        _restore_default_branch(working_dir, base_branch, to_commit, branch_name)
        raise
    # APP-33 contract: success must also leave the working copy on the default
    # branch so the next sync pull is not wedged once the PR merges and the
    # remote feature branch is deleted. Best-effort (_git never raises); the PR
    # already exists, so a failed checkout-back must not lose result.pr.
    _git(["checkout", base_branch], working_dir)
    _git(["branch", "-D", branch_name], working_dir)
    return result
