# AI-10 Inventory Pass Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the inventory-pass orchestrator: run the AI per-policy extraction across an ingested manifest, emit `policies/<slug>.md` + `policies/<slug>.audit.yaml` drafts into the diocese working copy, and open one bulk draft PR.

**Architecture:** Three new pieces. (1) `ai/inventory_extract.py` is the generic, diocese-agnostic per-policy extraction core, mirroring `ai/retention_extract.py` (routed through `ai.provider.LLMProvider`, unit-testable without a network call). (2) `ai/inventory.py` is the Django-free orchestrator: iterate the manifest, extract text via `ingest.extractors.extract`, run the metadata extraction, emit markdown via `ai.emit` + audit sidecar via `ai.audit`, skip slugs that already exist, then `branch -> commit -> push -> open_pr` for one bulk PR (mirrors `app/onboarding/finalize.py`). (3) `core/management/commands/run_inventory_pass.py` is the thin CLI that wires `LocalFolderConnector` -> manifest -> taxonomy load -> `run_inventory_pass`.

**Tech Stack:** Python 3, pytest / pytest-django, PyYAML, the Anthropic SDK (only at the live edge, mocked in tests), Django management commands.

**Confirmed design decisions (Chuck, 2026-06-05):**
- Invocation: Django management command + Django-free library core.
- Re-run: skip any slug that already exists (flat `.md` or a bundle dir); never clobber human edits or the foundational `document-retention` bundle.
- Audit sidecars: `<slug>.audit.yaml` committed alongside the `<slug>.md` in the same bulk PR (Astro renders only `.md`, so they don't leak into the handbook).
- Extraction core: new generic `ai/inventory_extract.py`, NOT an import from PT-flavored `spike/extract.py`.

**Conventions for the implementer:**
- Test interpreter is `ai/venv/bin/python` (no root venv exists). Run tests as e.g. `ai/venv/bin/python -m pytest ai/tests/test_inventory_extract.py -v`.
- Commit straight to `main` after each task (trunk-based repo). Use `>=` floor constraints if you ever touch a requirements file (you will not in this plan).
- "Ship generic, never PT-flavored": no diocese name, no "Pensacola", no "PT" in any shipping string (prompts, messages, comments, class names).

---

## File Structure

| File | Responsibility | New/Modified |
|------|----------------|--------------|
| `ai/inventory_extract.py` | Generic per-policy metadata extraction: prompt build, response parse, `extract_policy_metadata(provider, text, taxonomy)`. | Create |
| `ai/tests/test_inventory_extract.py` | Unit tests for the extraction core (FakeProvider, no network). | Create |
| `ai/inventory.py` | Orchestrator: `run_inventory_pass(...)`, `_slugify`, `make_inventory_branch_name`, `InventoryResult`. | Create |
| `ai/tests/test_inventory.py` | Unit tests for the orchestrator (FakeGitProvider + FakeLLMProvider + tmp working copy). | Create |
| `core/management/commands/run_inventory_pass.py` | Thin CLI: folder -> manifest -> taxonomy -> `run_inventory_pass`; report. | Create |
| `core/tests/test_run_inventory_pass_command.py` | Command-level wiring tests via `call_command` (boundary-mocked). | Create |

No existing files are modified by the code tasks. Status-doc updates (`PolicyWonk-v0.1-Tickets.md`, `CLAUDE.md`, Daily Log) are controller wrap-up, listed in Task 6.

---

## Task 1: Generic per-policy extraction core (`ai/inventory_extract.py`)

**Files:**
- Create: `ai/inventory_extract.py`
- Test: `ai/tests/test_inventory_extract.py`

- [ ] **Step 1: Write the failing test**

Create `ai/tests/test_inventory_extract.py`:

```python
"""Unit tests for the generic per-policy inventory extraction (AI-10)."""
import json

import pytest

from ai.inventory_extract import (
    EXTRACTION_MAX_TOKENS,
    InventoryExtractionError,
    build_inventory_prompt,
    build_taxonomy_section,
    extract_policy_metadata,
    parse_inventory_response,
)

VALID_EXTRACTION = {
    "title": "IT Acceptable Use Policy",
    "summary": "Governs staff use of diocesan computing resources.",
    "category": "IT",
    "category_confidence": "high",
    "owner_role": "IT Director",
    "owner_role_confidence": "high",
    "effective_date": "2021-01-01",
    "retention_period_years": 7,
    "suggested_chapter_section_item": "5.2.8",
    "address_confidence": "medium",
    "version_stamp": "1.0",
    "notes": "",
}

TAXONOMY = {
    "classifications": [
        {"id": "finance", "name": "Finance"},
        {"id": "it", "name": "Information Technology"},
    ],
    "retention_schedule": [
        {"group": "Financial Records", "type": "Audited statements", "retention": "Permanent"},
        {"group": "IT Records", "sub_group": "Access logs", "type": "Auth logs", "retention": "1 year"},
    ],
}


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text."""
    def __init__(self, text):
        self._text = text
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self._text


def test_parse_plain_json():
    assert parse_inventory_response(json.dumps(VALID_EXTRACTION)) == VALID_EXTRACTION


def test_parse_strips_code_fences():
    raw = "```json\n" + json.dumps(VALID_EXTRACTION) + "\n```"
    assert parse_inventory_response(raw) == VALID_EXTRACTION


def test_parse_rejects_non_json():
    with pytest.raises(InventoryExtractionError, match="JSON"):
        parse_inventory_response("this is not json")


def test_parse_rejects_non_object():
    with pytest.raises(InventoryExtractionError, match="object"):
        parse_inventory_response(json.dumps(["a", "b"]))


def test_parse_requires_title():
    no_title = {k: v for k, v in VALID_EXTRACTION.items() if k != "title"}
    with pytest.raises(InventoryExtractionError, match="title"):
        parse_inventory_response(json.dumps(no_title))


def test_taxonomy_section_is_generic():
    section = build_taxonomy_section(TAXONOMY)
    # Ship-generic: no diocese name leaks into the prompt.
    assert "Pensacola" not in section
    assert "PT" not in section
    assert "finance: Finance" in section
    assert "Financial Records: Audited statements -> Permanent" in section
    # sub_group rows render "group / sub_group".
    assert "IT Records / Access logs: Auth logs -> 1 year" in section


def test_taxonomy_section_dedupes_group_pairs():
    taxonomy = {
        "classifications": [],
        "retention_schedule": [
            {"group": "G", "type": "A", "retention": "1 year"},
            {"group": "G", "type": "B", "retention": "2 years"},
        ],
    }
    section = build_taxonomy_section(taxonomy)
    # One example per (group, sub_group) pair: only the first row of group G appears.
    assert section.count("G: ") == 1


def test_build_prompt_without_taxonomy_omits_section():
    prompt = build_inventory_prompt(None)
    assert "taxonomy reference" not in prompt
    assert "Output strictly as JSON" in prompt


def test_build_prompt_with_taxonomy_includes_section():
    prompt = build_inventory_prompt(TAXONOMY)
    assert "taxonomy reference" in prompt
    assert "Output strictly as JSON" in prompt


def test_extract_policy_metadata_calls_provider_and_parses():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    result = extract_policy_metadata(provider, "document body text", TAXONOMY)
    assert result == VALID_EXTRACTION
    assert provider.last_max_tokens == EXTRACTION_MAX_TOKENS
    assert "document body text" in provider.last_prompt
    assert "taxonomy reference" in provider.last_prompt


def test_extract_truncates_long_document():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    extract_policy_metadata(provider, "x" * 100000, None)
    # The injected document text is capped; the prompt cannot carry the whole 100k.
    assert provider.last_prompt.count("x") <= 50000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai.inventory_extract'`

- [ ] **Step 3: Write the implementation**

Create `ai/inventory_extract.py`:

```python
"""Generic per-policy inventory extraction (AI-10).

The shipping counterpart to spike/extract.py's single-document metadata
extraction: given one governing document's text plus the diocese's taxonomy,
return the structured per-policy metadata dict that ai/emit.py and ai/audit.py
turn into policies/<slug>.md + policies/<slug>.audit.yaml.

Diocese-agnostic ("the diocese", never a named diocese) and routed through
ai.provider.LLMProvider, so it is unit-testable without a network call and
ships generic per the project's "ship generic, never PT-flavored" rule.
"""
from __future__ import annotations

import json
from typing import Any

from ai.provider import LLMProvider

# Output budget per policy; mirrors spike/extract.py's max_tokens.
EXTRACTION_MAX_TOKENS = 2048

# Cap injected document text so the prompt stays within budget. A very long
# policy is truncated here; chunked extraction is a post-DISC item.
MAX_DOCUMENT_CHARS = 50000

_PROMPT_HEADER = """\
You are a policy librarian for a Catholic diocese. You read a single
governing document (policy, procedure, or by-law) and extract structured
metadata. Be conservative. If a field is not stated or strongly implied
in the text, leave it null and lower your confidence.

"""

_PROMPT_TAXONOMY_GUIDANCE = """\
When extracting `category` and `suggested_chapter_section_item`, PREFER
values that align with the diocese taxonomy above. Map your category
choice to one of the schema-defined category values (Finance, HR, IT,
Safe Environment, Schools, Worship, Parish Operations, Stewardship,
By-Laws, Communications, Risk, Other) but choose the one whose meaning
most closely matches the relevant classification or retention group.
For `suggested_chapter_section_item`, use a chapter.section.item address
(e.g., 5.2.8) where the chapter aligns with the classification axis or
retention group most relevant to the policy. If the policy doesn't
cleanly fit any provided category or group, use your best judgment and
note this in `notes`.

"""

_PROMPT_SCHEMA = """\
Output strictly as JSON, matching this schema:

{
  "title": "<the policy's title as best you can identify>",
  "summary": "<one sentence describing what this policy governs>",
  "category": "<one of: Finance, HR, IT, Safe Environment, Schools, Worship, Parish Operations, Stewardship, By-Laws, Communications, Risk, Other>",
  "category_confidence": "<low | medium | high>",
  "owner_role": "<best guess at the diocesan role responsible: CFO, HR Director, IT Director, Vicar General, Chancellor, Superintendent of Schools, Director of Safe Environment, etc.>",
  "owner_role_confidence": "<low | medium | high>",
  "effective_date": "<ISO date if stated, else null>",
  "effective_date_confidence": "<low | medium | high>",
  "last_review_date": "<ISO date if stated, else null>",
  "last_review_date_confidence": "<low | medium | high>",
  "next_review_date": "<ISO date if stated, or computed from effective date plus implied cadence, else null>",
  "next_review_date_confidence": "<low | medium | high>",
  "retention_period_years": "<integer years if stated or inferable from records-management norms, else null>",
  "retention_period_confidence": "<low | medium | high>",
  "suggested_chapter_section_item": "<chapter.section.item address using chapter.section.item numbering, e.g., 5.2.8>",
  "address_confidence": "<low | medium | high>",
  "version_stamp": "1.0",
  "notes": "<anything ambiguous, missing, or concerning that a human reviewer should know>"
}

Document text follows. Output only the JSON object.
---
"""


class InventoryExtractionError(ValueError):
    """The model output could not be read as a per-policy extraction."""


def build_taxonomy_section(taxonomy: dict[str, Any]) -> str:
    """Render the diocese taxonomy into a prompt section.

    Lists all top-level classifications and one example retention row per
    (group, sub_group) pair, in YAML order, keeping the prompt budget bounded
    while covering every department. Diocese-agnostic: no diocese name.
    """
    lines = ["## Diocese taxonomy reference", ""]
    lines.append("Top-level data classifications:")
    for entry in taxonomy.get("classifications", []):
        lines.append(f"- {entry['id']}: {entry['name']}")
    lines.append("")
    lines.append("Retention schedule (one example per group/sub-group):")
    seen: set[tuple[str, str | None]] = set()
    for row in taxonomy.get("retention_schedule", []):
        pair = (row["group"], row.get("sub_group"))
        if pair in seen:
            continue
        seen.add(pair)
        label = row["group"]
        if row.get("sub_group"):
            label = f"{label} / {row['sub_group']}"
        lines.append(f"- {label}: {row['type']} -> {row['retention']}")
    lines.append("")
    return "\n".join(lines)


def build_inventory_prompt(taxonomy: dict[str, Any] | None) -> str:
    """Assemble the full extraction prompt.

    When `taxonomy` is None (no foundational bundle present), the taxonomy
    section and its guidance paragraph are omitted; extraction still runs but
    without retention/address grounding.
    """
    if taxonomy:
        return (
            _PROMPT_HEADER
            + build_taxonomy_section(taxonomy)
            + "\n"
            + _PROMPT_TAXONOMY_GUIDANCE
            + _PROMPT_SCHEMA
        )
    return _PROMPT_HEADER + _PROMPT_SCHEMA


def parse_inventory_response(raw: str) -> dict[str, Any]:
    """Parse the model's text into an extraction dict, or raise InventoryExtractionError."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InventoryExtractionError(f"model did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InventoryExtractionError("model JSON was not an object")
    if not parsed.get("title"):
        raise InventoryExtractionError("model JSON missing required 'title'")
    return parsed


def extract_policy_metadata(
    provider: LLMProvider, document_text: str, taxonomy: dict[str, Any] | None
) -> dict[str, Any]:
    """Run the extraction prompt against a single document's text."""
    prompt = build_inventory_prompt(taxonomy) + document_text[:MAX_DOCUMENT_CHARS]
    raw = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    return parse_inventory_response(raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory_extract.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add ai/inventory_extract.py ai/tests/test_inventory_extract.py
git commit -m "feat(ai): generic per-policy inventory extraction core (AI-10)"
```

---

## Task 2: Orchestrator pure helpers (`ai/inventory.py` part 1)

**Files:**
- Create: `ai/inventory.py`
- Test: `ai/tests/test_inventory.py`

- [ ] **Step 1: Write the failing test**

Create `ai/tests/test_inventory.py`:

```python
"""Unit tests for the AI-10 inventory-pass orchestrator."""
import re

from ai.inventory import (
    InventoryResult,
    REQUIRED_CAPABILITIES,
    _slugify,
    make_inventory_branch_name,
)


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
    assert result.skipped_empty == []
    assert result.skipped_unsupported == []
    assert result.errors == {}
    assert result.pr is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai.inventory'`

- [ ] **Step 3: Write the implementation**

Create `ai/inventory.py`:

```python
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
from pathlib import Path
from typing import Any

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add ai/inventory.py ai/tests/test_inventory.py
git commit -m "feat(ai): inventory orchestrator helpers (slug, branch, result) (AI-10)"
```

---

## Task 3: `run_inventory_pass` happy path (`ai/inventory.py` part 2)

**Files:**
- Modify: `ai/inventory.py` (append `run_inventory_pass` + `_build_pr_body`)
- Test: `ai/tests/test_inventory.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `ai/tests/test_inventory.py`:

```python
import json
from pathlib import Path

import pytest

from ai.inventory import run_inventory_pass
from ingest.manifest import ManifestEntry


class FakeLLM:
    """Returns a canned extraction JSON, varying title by call count."""
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, max_tokens):
        self.calls += 1
        return json.dumps({
            "title": f"Policy {self.calls}",
            "summary": "A summary.",
            "category": "IT",
            "category_confidence": "high",
            "retention_period_years": 7,
            "version_stamp": "1.0",
        })


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
    # Each policy gets a .md and a .audit.yaml in the working copy.
    assert (work / "policies" / "acceptable-use.md").exists()
    assert (work / "policies" / "acceptable-use.audit.yaml").exists()
    assert (work / "policies" / "by-laws.md").exists()
    assert (work / "policies" / "by-laws.audit.yaml").exists()
    # The .md carries front matter; the .audit.yaml carries a confidence map.
    assert (work / "policies" / "acceptable-use.md").read_text().startswith("---\n")
    assert "confidence:" in (work / "policies" / "acceptable-use.audit.yaml").read_text()

    # Exactly ONE bulk PR, with all four files in one commit.
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory.py::test_happy_path_writes_drafts_and_opens_one_bulk_pr -v`
Expected: FAIL with `ImportError: cannot import name 'run_inventory_pass'`

- [ ] **Step 3: Write the implementation**

Append to `ai/inventory.py`:

```python
def _build_pr_body(result: "InventoryResult", username: str) -> str:
    lines = [
        f"Opened by PolicyCodex inventory pass on behalf of {username}.",
        "",
        f"Drafted {len(result.written)} policies:",
    ]
    lines += [f"- policies/{slug}.md" for slug in result.written]
    if result.skipped_existing:
        lines += ["", f"Skipped {len(result.skipped_existing)} already present:"]
        lines += [f"- {slug}" for slug in result.skipped_existing]
    if result.errors:
        lines += ["", f"{len(result.errors)} extraction errors (not committed):"]
        lines += [f"- {slug}: {msg}" for slug, msg in result.errors.items()]
    return "\n".join(lines) + "\n"


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
    username: str = "PolicyCodex",
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

    for entry in manifest:
        slug = _slugify(entry.path.stem)
        md_path = policies_dir / f"{slug}.md"
        audit_path = policies_dir / f"{slug}.audit.yaml"
        bundle_dir = policies_dir / slug

        # Skip-existing: never clobber a flat policy or a foundational bundle.
        if md_path.exists() or bundle_dir.is_dir():
            result.skipped_existing.append(slug)
            continue

        try:
            text = extract(entry.path)
        except UnsupportedFormatError:
            result.skipped_unsupported.append(entry.path.name)
            continue
        if not text.strip():
            result.skipped_empty.append(entry.path.name)
            continue

        try:
            metadata = extract_policy_metadata(llm_provider, text, taxonomy)
        except InventoryExtractionError as exc:
            # One bad extraction must not discard the rest of the run.
            result.errors[slug] = str(exc)
            continue

        metadata["_source_file"] = entry.path.name
        md_path.write_text(emit.to_markdown(metadata), encoding="utf-8")
        audit_path.write_text(audit.to_audit_yaml(metadata), encoding="utf-8")
        to_commit.extend([md_path, audit_path])
        result.written.append(slug)

    if not to_commit:
        return result

    branch_name = make_inventory_branch_name()
    message = f"Inventory pass: add {len(result.written)} draft policies"
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
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add ai/inventory.py ai/tests/test_inventory.py
git commit -m "feat(ai): run_inventory_pass writes drafts + opens one bulk PR (AI-10)"
```

---

## Task 4: `run_inventory_pass` edge cases

**Files:**
- Test: `ai/tests/test_inventory.py` (append)
- No implementation changes expected (Task 3 already handles these); if a test fails, fix `ai/inventory.py`.

- [ ] **Step 1: Write the failing test**

Append to `ai/tests/test_inventory.py`:

```python
class BadLLM:
    """Always returns unparseable output."""
    def complete(self, prompt, max_tokens):
        return "not json at all"


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
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory.py -v`
Expected: PASS for all (Task 3's implementation already covers these). If any FAIL, fix `ai/inventory.py` to satisfy the assertion, then re-run.

- [ ] **Step 3: Commit**

```bash
git add ai/tests/test_inventory.py
git commit -m "test(ai): inventory pass skip/error/empty edge cases (AI-10)"
```

---

## Task 5: Management command (`core/management/commands/run_inventory_pass.py`)

**Files:**
- Create: `core/management/commands/run_inventory_pass.py`
- Test: `core/tests/test_run_inventory_pass_command.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_run_inventory_pass_command.py`:

```python
"""Wiring tests for the run_inventory_pass management command (AI-10).

The orchestrator itself is tested in ai/tests/test_inventory.py; here we only
assert the Django-side wiring: taxonomy presence is enforced, and the loaded
manifest + taxonomy + config are handed to run_inventory_pass.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

import core.management.commands.run_inventory_pass as cmd
from ai.inventory import InventoryResult


@pytest.fixture
def patched(monkeypatch, tmp_path):
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)
    config = SimpleNamespace(working_dir=work, branch="main")
    monkeypatch.setattr(cmd, "load_working_copy_config", lambda: config)
    monkeypatch.setattr(cmd, "GitHubProvider", lambda: "GITHUB")
    monkeypatch.setattr(cmd, "ClaudeProvider", lambda: "CLAUDE")

    # A connector that yields two fake files.
    files = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    for f in files:
        f.write_text("x", encoding="utf-8")

    class FakeConnector:
        def __init__(self, root):
            self.root = root

        def walk(self):
            return iter(files)

    monkeypatch.setattr(cmd, "LocalFolderConnector", FakeConnector)
    monkeypatch.setattr(cmd, "build_manifest", lambda paths, label: list(paths))
    return SimpleNamespace(work=work, files=files, config=config)


def test_errors_when_no_foundational_bundle(monkeypatch, patched, tmp_path):
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: None)
    with pytest.raises(CommandError, match="foundational"):
        call_command("run_inventory_pass", str(tmp_path))


def test_happy_path_calls_orchestrator_with_loaded_inputs(monkeypatch, patched, tmp_path):
    taxonomy = {"classifications": [], "retention_schedule": []}
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: taxonomy)

    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return InventoryResult(written=["a", "b"], pr={"url": "https://example/pr/9"})

    monkeypatch.setattr(cmd, "run_inventory_pass", fake_run)
    call_command("run_inventory_pass", str(tmp_path))

    assert captured["taxonomy"] is taxonomy
    assert captured["base_branch"] == "main"
    assert captured["provider"] == "GITHUB"
    assert captured["llm_provider"] == "CLAUDE"
    assert captured["author_name"] == "PolicyCodex"
    assert len(captured["manifest"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest core/tests/test_run_inventory_pass_command.py -v`
Expected: FAIL with `ModuleNotFoundError` for `core.management.commands.run_inventory_pass`

- [ ] **Step 3: Write the implementation**

Create `core/management/commands/run_inventory_pass.py`:

```python
"""Run the AI inventory pass over a local folder of policy files (AI-10).

Wires the ingest pipeline to the orchestrator: walk the source folder, build a
manifest, load the diocese's live foundational taxonomy from the working copy,
and hand everything to ai.inventory.run_inventory_pass, which writes draft
markdown + audit sidecars and opens one bulk draft PR.

Precondition: the working copy must be synced (run `manage.py
pull_working_copy` first) and must already contain the document-retention
foundational bundle (scaffolded during onboarding). The taxonomy is required so
extraction has retention/address grounding.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai.claude_provider import ClaudeProvider
from ai.inventory import REQUIRED_CAPABILITIES, run_inventory_pass
from ai.taxonomy_loader import load_foundational_taxonomy
from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from ingest.local_folder import LocalFolderConnector
from ingest.manifest import build_manifest


class Command(BaseCommand):
    help = "Run the AI inventory pass over a local folder; open one bulk draft PR."

    def add_arguments(self, parser):
        parser.add_argument("source_folder", help="Folder of policy files to ingest.")
        parser.add_argument("--author-name", default="PolicyCodex")
        parser.add_argument("--author-email", default="bot@policycodex.local")
        parser.add_argument("--source-label", default="local-folder")

    def handle(self, *args, **options):
        config = load_working_copy_config()
        working_dir = Path(config.working_dir)
        policies_dir = working_dir / "policies"

        taxonomy = load_foundational_taxonomy(policies_dir, REQUIRED_CAPABILITIES)
        if taxonomy is None:
            raise CommandError(
                f"No foundational retention bundle found under {policies_dir}. "
                "Complete onboarding so the document-retention bundle exists, "
                "then re-run; extraction needs the retention schedule for grounding."
            )

        source = Path(options["source_folder"])
        paths = list(LocalFolderConnector(source).walk())
        manifest = build_manifest(paths, options["source_label"])

        result = run_inventory_pass(
            manifest=manifest,
            working_dir=working_dir,
            provider=GitHubProvider(),
            llm_provider=ClaudeProvider(),
            taxonomy=taxonomy,
            author_name=options["author_name"],
            author_email=options["author_email"],
            base_branch=config.branch,
        )
        self._report(result)

    def _report(self, result):
        self.stdout.write(self.style.SUCCESS(
            f"wrote {len(result.written)} drafts; "
            f"skipped {len(result.skipped_existing)} existing, "
            f"{len(result.skipped_empty)} empty, "
            f"{len(result.skipped_unsupported)} unsupported; "
            f"{len(result.errors)} extraction errors"
        ))
        if result.errors:
            for slug, msg in result.errors.items():
                self.stdout.write(self.style.WARNING(f"  error {slug}: {msg}"))
        if result.pr:
            self.stdout.write(self.style.SUCCESS(f"opened PR: {result.pr.get('url')}"))
        else:
            self.stdout.write("no PR opened (nothing new to draft)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest core/tests/test_run_inventory_pass_command.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/management/commands/run_inventory_pass.py core/tests/test_run_inventory_pass_command.py
git commit -m "feat(core): run_inventory_pass management command wires ingest -> orchestrator (AI-10)"
```

---

## Task 6: Full-suite verification + controller wrap-up

**Files:**
- No new code. Verification + status docs (controller does the status docs after review/merge).

- [ ] **Step 1: Run the full suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS, suite count up by ~27 from the pre-AI-10 baseline (463). Report the exact before/after count.

- [ ] **Step 2: Confirm ship-generic (no PT leakage in new shipping code)**

Run: `grep -rniE "pensacola|ptdiocese|\bPT\b" ai/inventory.py ai/inventory_extract.py core/management/commands/run_inventory_pass.py`
Expected: no matches (the test files may reference fixtures, but shipping modules must be clean).

- [ ] **Step 3: Controller wrap-up (NOT the implementer subagent)**

After two-stage review passes and the work merges to `main`:
- Mark AI-10 resolved in `PolicyWonk-v0.1-Tickets.md` (commit range, the four confirmed decisions, suite delta, this plan path).
- Update the `## Current Status` line in `CLAUDE.md` (suite count; AI-10 done; remaining Week-5 items: REPO-11/12, INGEST-05/06).
- Append an event to `internal/PolicyWonk-Daily-Log.md`.

---

## Self-Review

**1. Spec coverage.**
- Spec P0.2 "for each ingested file, propose [metadata]... output as markdown with YAML front matter" -> Task 1 (extraction) + Task 3 (emit via `ai.emit`). Covered.
- Spec acceptance line 128 "markdown file with complete YAML front matter is staged for commit, with confidence scores in a separate audit file" -> Task 3 writes `<slug>.md` (emit strips confidence) + `<slug>.audit.yaml` (audit keeps confidence), both committed. Covered.
- Spec line 125 "extraction prompt receives the diocese's chosen address taxonomy + source-of-truth references" -> taxonomy injected via `build_inventory_prompt(taxonomy)`; command loads it from the live bundle via `load_foundational_taxonomy`. Covered.
- Ticket AI-10 "commits markdown to the diocese policy repo as initial drafts" + lane acceptance "commits on a draft branch, opens a single bulk PR" -> Task 3 one bulk PR on a non-slug-mapped `policycodex/inventory-<hex>` branch. Covered.
- Ship-generic principle -> new generic extraction module (not spike import); Task 6 grep gate. Covered.

**2. Placeholder scan.** No TBD/TODO; every code step shows complete code; every test shows real assertions. Clean.

**3. Type consistency.** `extract_policy_metadata(provider, document_text, taxonomy)`, `parse_inventory_response(raw)`, `build_inventory_prompt(taxonomy)`, `build_taxonomy_section(taxonomy)`, `InventoryExtractionError` — names identical across Task 1 module, Task 1 tests, and Task 3 consumer. `run_inventory_pass(*, manifest, working_dir, provider, llm_provider, taxonomy, author_name, author_email, base_branch, username)` — identical signature in Task 3 impl, Task 3/4 tests, and the Task 5 command call (command omits `username`, which defaults to "PolicyCodex"). `InventoryResult` fields (`written`, `skipped_existing`, `skipped_empty`, `skipped_unsupported`, `errors`, `pr`) — identical in Task 2 dataclass, Task 3/4 tests, and Task 5 `_report`. `REQUIRED_CAPABILITIES` matches `ai/taxonomy_loader` usage and `spike/extract.py`. Provider method names (`branch`, `commit`, `push`, `open_pr`) match `app/git_provider/base.py`. Consistent.

---

## Execution Handoff

**Plan complete and saved to `internal/superpowers/plans/2026-06-05-ai-10-inventory-pass-orchestrator.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Matches the project's default (implementers directly on `main`, sequential, two-stage review, controller-applies-fixes).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
