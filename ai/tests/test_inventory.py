"""Unit tests for the AI-10 inventory-pass orchestrator."""
import json
import re
from pathlib import Path

import pytest

from ai.inventory import (
    InventoryResult,
    REQUIRED_CAPABILITIES,
    _slugify,
    make_inventory_branch_name,
    run_inventory_pass,
)
from ai.provider import CompletionResult, Usage
from ingest.manifest import ManifestEntry

_FAKE_USAGE = Usage("fake", "m", 1, 2, "2026-06-08T00:00:00+00:00")


def test_required_capabilities():
    assert REQUIRED_CAPABILITIES == ("classifications", "retention-schedule")


def test_slugify_basic():
    assert _slugify("IT Acceptable Use Policy") == "it-acceptable-use-policy"


def test_slugify_strips_punctuation_and_collapses():
    assert _slugify("By-Laws (2021): Final!!") == "by-laws-2021-final"


def test_slugify_empty_falls_back():
    assert _slugify("   ") == "policy"
    assert _slugify("@@@") == "policy"


def test_make_inventory_branch_name_is_not_slug_mapped():
    from app.git_provider.states import branch_to_slug

    name = make_inventory_branch_name()
    assert re.fullmatch(r"policycodex/inventory-[0-9a-f]{8}", name)
    # Deliberately NOT slug-mapped: the catalog gate lookup must ignore this
    # bulk-import branch (mirrors the onboarding init branch).
    assert branch_to_slug(name) is None


def test_inventory_result_defaults_empty():
    result = InventoryResult()
    assert result.written == []
    assert result.skipped_existing == []
    assert result.skipped_collision == []
    assert result.skipped_empty == []
    assert result.skipped_unsupported == []
    assert result.errors == {}
    assert result.pr is None


class FakeLLM:
    """Returns a canned extraction JSON, varying title by call count."""
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, max_tokens):
        self.calls += 1
        text = json.dumps({
            "title": f"Policy {self.calls}",
            "summary": "A summary.",
            "category": "IT",
            "category_confidence": "high",
            "retention_period_years": 7,
            "version_stamp": "1.0",
        })
        return CompletionResult(text=text, usage=_FAKE_USAGE)


class FakeGitProvider:
    """Records branch/commit/push/open_pr calls; opens one fake PR."""
    def __init__(self):
        self.branch_calls = []
        self.commit_calls = []
        self.push_calls = []
        self.open_pr_calls = []

    def branch(self, name, working_dir):
        self.branch_calls.append(name)

    def commit(self, message, files, author_name, author_email, working_dir):
        self.commit_calls.append({
            "message": message, "files": list(files),
            "author_name": author_name, "author_email": author_email,
        })
        return "deadbeef"

    def push(self, branch, working_dir):
        self.push_calls.append(branch)

    def open_pr(self, title, body, head_branch, base_branch, working_dir):
        self.open_pr_calls.append({
            "title": title, "body": body,
            "head_branch": head_branch, "base_branch": base_branch,
        })
        return {"pr_number": 42, "url": "https://example/pr/42", "state": "open"}


def _src(tmp_path: Path, name: str, body: str = "Real policy text.") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _manifest(*paths: Path) -> list[ManifestEntry]:
    return [
        ManifestEntry(path=p, content_hash="h", last_modified=0.0, source_label="local-folder")
        for p in paths
    ]


def test_happy_path_writes_drafts_and_opens_one_bulk_pr(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    manifest = _manifest(_src(src_dir, "acceptable-use.txt"), _src(src_dir, "by-laws.md"))
    provider = FakeGitProvider()
    llm = FakeLLM()

    result = run_inventory_pass(
        manifest=manifest,
        working_dir=work,
        provider=provider,
        llm_provider=llm,
        taxonomy=None,
        author_name="PolicyCodex",
        author_email="bot@policycodex.local",
        base_branch="main",
        username="PolicyCodex",
    )

    assert result.written == ["acceptable-use", "by-laws"]
    assert (work / "policies" / "acceptable-use.md").exists()
    assert (work / "policies" / "acceptable-use.audit.yaml").exists()
    assert (work / "policies" / "by-laws.md").exists()
    assert (work / "policies" / "by-laws.audit.yaml").exists()
    assert (work / "policies" / "acceptable-use.md").read_text().startswith("---\n")
    assert "confidence:" in (work / "policies" / "acceptable-use.audit.yaml").read_text()

    assert len(provider.branch_calls) == 1
    assert provider.branch_calls[0].startswith("policycodex/inventory-")
    assert len(provider.commit_calls) == 1
    committed = {p.name for p in provider.commit_calls[0]["files"]}
    assert committed == {
        "acceptable-use.md", "acceptable-use.audit.yaml",
        "by-laws.md", "by-laws.audit.yaml",
    }
    assert provider.commit_calls[0]["author_name"] == "PolicyCodex"
    assert provider.push_calls == provider.branch_calls
    assert len(provider.open_pr_calls) == 1
    assert provider.open_pr_calls[0]["base_branch"] == "main"
    assert result.pr == {"pr_number": 42, "url": "https://example/pr/42", "state": "open"}


class BadLLM:
    """Always returns unparseable output."""
    def complete(self, prompt, max_tokens):
        return CompletionResult(text="not json at all", usage=_FAKE_USAGE)


def test_skips_existing_md_and_bundle_without_clobbering(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    policies = work / "policies"
    policies.mkdir(parents=True)

    # Pre-existing flat policy and a foundational bundle dir.
    (policies / "by-laws.md").write_text("ORIGINAL HUMAN EDIT", encoding="utf-8")
    (policies / "document-retention").mkdir()
    (policies / "document-retention" / "policy.md").write_text("x", encoding="utf-8")

    manifest = _manifest(
        _src(src_dir, "by-laws.txt"),             # collides with existing .md
        _src(src_dir, "document-retention.pdf"),  # collides with bundle dir
        _src(src_dir, "fresh.txt"),               # new -> written
    )
    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=manifest, working_dir=work, provider=provider,
        llm_provider=FakeLLM(), taxonomy=None,
        author_name="PolicyCodex", author_email="bot@policycodex.local",
        base_branch="main",
    )

    assert result.written == ["fresh"]
    assert set(result.skipped_existing) == {"by-laws", "document-retention"}
    # The human edit is untouched.
    assert (policies / "by-laws.md").read_text() == "ORIGINAL HUMAN EDIT"
    # Only the new policy's files are committed.
    committed = {p.name for p in provider.commit_calls[0]["files"]}
    assert committed == {"fresh.md", "fresh.audit.yaml"}


def test_skips_empty_text_and_unsupported_format(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    blank = _src(src_dir, "blank.txt", body="   \n  ")
    unsupported = _src(src_dir, "weird.xyz", body="content")
    good = _src(src_dir, "good.txt")

    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=_manifest(blank, unsupported, good),
        working_dir=work, provider=provider, llm_provider=FakeLLM(),
        taxonomy=None, author_name="PolicyCodex",
        author_email="bot@policycodex.local", base_branch="main",
    )

    assert result.written == ["good"]
    assert result.skipped_empty == ["blank.txt"]
    assert result.skipped_unsupported == ["weird.xyz"]


def test_extraction_error_is_captured_not_fatal(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=_manifest(_src(src_dir, "broken.txt")),
        working_dir=work, provider=provider, llm_provider=BadLLM(),
        taxonomy=None, author_name="PolicyCodex",
        author_email="bot@policycodex.local", base_branch="main",
    )

    assert result.written == []
    assert "broken" in result.errors
    # Nothing written -> no branch/commit/PR.
    assert provider.branch_calls == []
    assert result.pr is None


def test_empty_manifest_opens_no_pr(tmp_path):
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)
    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=[], working_dir=work, provider=provider, llm_provider=FakeLLM(),
        taxonomy=None, author_name="PolicyCodex",
        author_email="bot@policycodex.local", base_branch="main",
    )
    assert result.written == []
    assert provider.open_pr_calls == []
    assert result.pr is None


def test_in_pass_slug_collision_is_surfaced_not_silently_dropped(tmp_path):
    # Two distinct source files that slugify to the same name: the first is
    # drafted; the second must be reported as a collision (a real document we
    # refused to clobber), NOT mislabeled as an already-present skip.
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    manifest = _manifest(
        _src(src_dir, "Finance Policy.txt"),   # -> finance-policy (first wins)
        _src(src_dir, "finance_policy.md"),    # -> finance-policy (collision)
    )
    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=manifest, working_dir=work, provider=provider,
        llm_provider=FakeLLM(), taxonomy=None, author_name="PolicyCodex",
        author_email="bot@policycodex.local", base_branch="main",
    )

    assert result.written == ["finance-policy"]
    assert result.skipped_collision == ["finance_policy.md"]
    assert result.skipped_existing == []
    # Only the first file's pair is committed; the collision is in the PR body.
    committed = {p.name for p in provider.commit_calls[0]["files"]}
    assert committed == {"finance-policy.md", "finance-policy.audit.yaml"}
    assert "slug collisions" in provider.open_pr_calls[0]["body"]


def test_corrupt_file_read_error_is_non_fatal(tmp_path, monkeypatch):
    # A read/extract failure other than UnsupportedFormatError on one file must
    # not sink the bulk pass; it lands in errors and the rest proceed.
    import ai.inventory as inv

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    good = _src(src_dir, "good.txt")
    corrupt = _src(src_dir, "corrupt.pdf")

    real_extract = inv.extract

    def flaky_extract(path):
        if path.name == "corrupt.pdf":
            raise RuntimeError("PdfReadError: stream truncated")
        return real_extract(path)

    monkeypatch.setattr(inv, "extract", flaky_extract)

    provider = FakeGitProvider()
    result = run_inventory_pass(
        manifest=_manifest(corrupt, good), working_dir=work, provider=provider,
        llm_provider=FakeLLM(), taxonomy=None, author_name="PolicyCodex",
        author_email="bot@policycodex.local", base_branch="main",
    )

    assert result.written == ["good"]
    assert "corrupt" in result.errors
    assert "read failed" in result.errors["corrupt"]
    # The good file still drafted and a PR still opened.
    assert result.pr is not None


# AI-17: changed_entries surfaces sources whose content changed since the last
# inventory without re-extracting them. The locked slug-exists guard already
# protects drafts; this new path makes the change VISIBLE.

def test_changed_entries_become_skipped_changed_without_llm_call(tmp_path):
    """run_inventory_pass with changed_entries=[entry] produces skipped_changed=[slug],
    makes no LLM call for that entry, writes no .md, and the PR body lists it
    in its own section above skipped_existing."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    new_source = _src(src_dir, "acceptable-use.txt")
    changed_source = _src(src_dir, "by-laws.md", body="Updated body since last run.")

    provider = FakeGitProvider()
    llm = FakeLLM()

    result = run_inventory_pass(
        manifest=_manifest(new_source),
        changed_entries=_manifest(changed_source),
        working_dir=work,
        provider=provider,
        llm_provider=llm,
        taxonomy=None,
        author_name="PolicyCodex",
        author_email="bot@policycodex.local",
        base_branch="main",
        username="PolicyCodex",
    )

    assert result.written == ["acceptable-use"]
    assert result.skipped_changed == ["by-laws"]
    # LLM called exactly once (for the new source), never for the changed one.
    assert llm.calls == 1
    # No draft file written for the changed source.
    assert not (work / "policies" / "by-laws.md").exists()
    assert not (work / "policies" / "by-laws.audit.yaml").exists()
    # The new source is committed; the changed source is not.
    assert len(provider.commit_calls) == 1
    committed = {p.name for p in provider.commit_calls[0]["files"]}
    assert committed == {"acceptable-use.md", "acceptable-use.audit.yaml"}
    # PR body lists the skipped_changed bucket above skipped_existing,
    # immediately after the written section.
    body = provider.open_pr_calls[0]["body"]
    assert "by-laws" in body
    assert "changed since last inventory" in body
    assert "Drafted 1 policies" in body
    written_idx = body.index("Drafted 1 policies")
    changed_idx = body.index("changed since last inventory")
    assert changed_idx > written_idx


def test_changed_entries_alone_does_not_open_a_pr(tmp_path):
    """Only skipped_changed (no new written) -> no commit, no branch, no PR."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)

    changed_source = _src(src_dir, "by-laws.md", body="Updated body.")

    provider = FakeGitProvider()
    llm = FakeLLM()

    result = run_inventory_pass(
        manifest=[],
        changed_entries=_manifest(changed_source),
        working_dir=work,
        provider=provider,
        llm_provider=llm,
        taxonomy=None,
        author_name="PolicyCodex",
        author_email="bot@policycodex.local",
        base_branch="main",
        username="PolicyCodex",
    )

    assert result.skipped_changed == ["by-laws"]
    assert result.written == []
    assert result.pr is None
    assert provider.branch_calls == []
    assert provider.commit_calls == []
    assert provider.push_calls == []
    assert provider.open_pr_calls == []
