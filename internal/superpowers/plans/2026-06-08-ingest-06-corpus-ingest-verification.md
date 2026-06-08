# INGEST-06: Corpus Ingest Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the ingest lane (walk -> extract -> manifest -> incremental diff) ingests the real v0.1 PT corpus end to end, via a corpus-gated integration test plus a captured real-corpus run.

**Architecture:** Add one new integration test module that composes the *existing* ingest components against a corpus folder located by the `POLICYCODEX_CORPUS_DIR` env var. The test auto-skips when the env var is unset or points at a missing dir, so CI stays green and no private PT data is required in the repo. Running it locally with the env var set to `~/.config/policycodex/corpus/pt/` exercises the real 19 PDFs; that run's result is recorded as evidence. No production code changes — INGEST-06 is verification of code shipped by INGEST-01..05.

**Tech Stack:** Python 3.14, pytest, pypdf 6.11 (already in `ai/venv`), the existing `ingest.local_folder`, `ingest.extractors`, `ingest.manifest`, `ingest.incremental` modules.

---

## Context the implementer needs

**The ingest lane being verified (all already exist, do not modify):**
- `ingest/local_folder.py` — `LocalFolderConnector(root).walk()` yields regular, non-hidden, non-symlink files recursively, sorted. Raises `RuntimeError` on an empty folder.
- `ingest/extractors/__init__.py` — `extract(path) -> str` dispatches by lowercase suffix. `.pdf` -> `PdfExtractor` (pypdf). Raises `UnsupportedFormatError` for unknown suffixes, `FileNotFoundError` for missing files.
- `ingest/manifest.py` — `build_manifest(paths, source_label) -> list[ManifestEntry]` (sorted by path; each entry has a SHA-256 `content_hash`). `ManifestEntry` fields: `path`, `content_hash`, `last_modified`, `source_label`. Also `diff_manifests`, `to_dict`/`from_dict`.
- `ingest/incremental.py` — `plan_incremental_run(root, manifest_path, source_label="local-folder") -> ManifestDiff` walks `root`, builds the current manifest, diffs it against the JSON manifest at `manifest_path` (missing file -> empty previous -> everything is `added`). `save_manifest(entries, path)` / `load_manifest(path)` persist JSON. `ManifestDiff` has `.added`, `.changed`, `.unchanged`, `.removed`, and the derived `.to_process` (added+changed) and `.current` (added+changed+unchanged).

**Corpus location:** `~/.config/policycodex/corpus/pt/` — 19 PT PDFs, flat, gitignored / out of the repo tree. Chuck moved them here 2026-06-08. This is the same local convention used for credentials, so private per-diocese data never enters the codebase.

**Why the env var, not a hardcoded path:** "Ship generic, never PT-flavored" (CLAUDE.md). The committed test must contain no PT specifics and no machine-specific absolute path. It reads `POLICYCODEX_CORPUS_DIR`, expands `~`, and skips if absent. The "19 PDFs all extract" fact is verified by the *run* (Task 3) and recorded in the Daily Log, not asserted as a magic number in committed code — so a different diocese can point the same env var at their own corpus and the test still holds.

**Test interpreter:** `ai/venv/bin/python` (no root venv exists; system python lacks pytest). Run pytest as `ai/venv/bin/python -m pytest ...` from the repo root `/Users/chuck/PolicyWonk`.

**Scope boundary — does NOT call the AI inventory pass.** `ai.inventory.run_inventory_pass` (AI-10) hits Claude (cost, network, non-determinism). INGEST-06 is an *ingest* ticket; it stops at the manifest and the extracted text. Keeping the AI pass out keeps this test deterministic and offline.

---

## File Structure

- Create: `ingest/tests/test_corpus_integration.py` — the entire deliverable. One module: an env-var gate (module constant + `skipif` marker) and the integration tests. All tests share the marker.
- Modify: none in product code.
- Docs to update at close: `internal/PolicyWonk-Daily-Log.md` (evidence), `PolicyWonk-v0.1-Tickets.md` (mark done), `CLAUDE.md` (status line).

---

### Task 1: Corpus gate + walk/extract coverage

**Files:**
- Create: `ingest/tests/test_corpus_integration.py`
- Test: same file (it *is* the test)

- [ ] **Step 1: Write the gate and the walk/extract tests**

Create `ingest/tests/test_corpus_integration.py` with exactly this content:

```python
"""End-to-end ingest verification against a real local corpus (INGEST-06).

Gated on POLICYCODEX_CORPUS_DIR: set it to a folder of source documents to
run; unset (CI default) -> these tests skip. The committed assertions are
corpus-agnostic (no hardcoded file count, no diocese specifics) so any
diocese can point the env var at their own corpus. The v0.1 PT-corpus run
(the 19 spike PDFs) is captured as evidence in the Daily Log, not asserted
here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ingest.extractors import extract
from ingest.local_folder import LocalFolderConnector

_CORPUS_ENV = "POLICYCODEX_CORPUS_DIR"
_raw = os.environ.get(_CORPUS_ENV)
CORPUS_DIR: Path | None = Path(_raw).expanduser() if _raw else None

corpus_required = pytest.mark.skipif(
    CORPUS_DIR is None or not CORPUS_DIR.is_dir(),
    reason=f"{_CORPUS_ENV} not set to an existing directory",
)


@corpus_required
def test_walk_yields_all_corpus_files():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    assert walked, "corpus walk yielded no files"
    assert len(walked) == len(set(walked)), "corpus walk yielded duplicates"
    for p in walked:
        assert p.is_file(), f"walk yielded a non-file: {p}"


@corpus_required
def test_every_corpus_file_extracts_nonempty_text():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    empties = []
    for p in walked:
        text = extract(p)
        if not text.strip():
            empties.append(p)
    assert not empties, f"extracted empty text from: {[str(p) for p in empties]}"
```

- [ ] **Step 2: Run without the env var to verify clean skip**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 2 skipped (reason: "POLICYCODEX_CORPUS_DIR not set to an existing directory"), 0 failed.

- [ ] **Step 3: Run with the env var to verify the real corpus passes**

Run: `POLICYCODEX_CORPUS_DIR=~/.config/policycodex/corpus/pt ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 2 passed, 0 skipped. (If `test_every_corpus_file_extracts_nonempty_text` fails, a real PDF produced no text — record which file; do not weaken the assertion without checking with Chuck.)

- [ ] **Step 4: Run the whole ingest suite to confirm no collateral breakage**

Run: `ai/venv/bin/python -m pytest ingest/ -q`
Expected: all pass, plus the 2 new tests skipped (env var unset in this invocation).

- [ ] **Step 5: Commit**

```bash
git add ingest/tests/test_corpus_integration.py
git commit -m "$(cat <<'EOF'
test(ingest-06): add corpus-gated walk+extract integration test

Verify the ingest lane against a real local corpus located by
POLICYCODEX_CORPUS_DIR; skips in CI when the env var is unset.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Manifest + incremental coverage over the corpus

**Files:**
- Modify: `ingest/tests/test_corpus_integration.py` (append two tests)
- Test: same file

- [ ] **Step 1: Append the manifest + incremental tests**

Add these imports to the existing import block at the top of `ingest/tests/test_corpus_integration.py`:

```python
from ingest.incremental import plan_incremental_run, save_manifest
from ingest.manifest import build_manifest
```

Append these two tests to the end of the file:

```python
@corpus_required
def test_manifest_has_one_hashed_entry_per_corpus_file():
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    entries = build_manifest(walked, source_label="corpus-test")
    assert len(entries) == len(walked)
    paths = [e.path for e in entries]
    assert len(set(paths)) == len(paths), "manifest has duplicate paths"
    for e in entries:
        assert len(e.content_hash) == 64, f"not a sha256 hex digest: {e.content_hash}"
        assert all(c in "0123456789abcdef" for c in e.content_hash)
        assert e.source_label == "corpus-test"


@corpus_required
def test_incremental_first_run_all_added_then_second_run_all_unchanged(tmp_path):
    walked = list(LocalFolderConnector(CORPUS_DIR).walk())
    manifest_path = tmp_path / "manifest.json"

    first = plan_incremental_run(CORPUS_DIR, manifest_path, source_label="corpus-test")
    assert len(first.added) == len(walked)
    assert first.changed == []
    assert first.removed == []
    assert len(first.to_process) == len(walked)

    save_manifest(first.current, manifest_path)

    second = plan_incremental_run(CORPUS_DIR, manifest_path, source_label="corpus-test")
    assert second.added == []
    assert second.changed == []
    assert second.removed == []
    assert len(second.unchanged) == len(walked)
    assert second.to_process == []
```

- [ ] **Step 2: Run with the env var to verify all four tests pass**

Run: `POLICYCODEX_CORPUS_DIR=~/.config/policycodex/corpus/pt ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 4 passed, 0 skipped.

- [ ] **Step 3: Run without the env var to verify clean skip**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 4 skipped, 0 failed.

- [ ] **Step 4: Commit**

```bash
git add ingest/tests/test_corpus_integration.py
git commit -m "$(cat <<'EOF'
test(ingest-06): cover manifest build + incremental re-run on the corpus

First run classifies every corpus file as added; after persisting the
manifest, a second run classifies every file as unchanged (nothing to
re-process).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Capture real-corpus evidence and close the ticket

**Files:**
- Modify: `internal/PolicyWonk-Daily-Log.md`
- Modify: `PolicyWonk-v0.1-Tickets.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Capture the corpus shape and counts from a real run**

Run: `POLICYCODEX_CORPUS_DIR=~/.config/policycodex/corpus/pt ai/venv/bin/python -m pytest ingest/tests/test_corpus_integration.py -v`
Expected: 4 passed. Note the pass count. Then capture the file count for the log:

Run: `find ~/.config/policycodex/corpus/pt -iname '*.pdf' | wc -l`
Expected: `19`.

- [ ] **Step 2: Append a Daily-Log entry**

Append a dated entry to `internal/PolicyWonk-Daily-Log.md` recording: INGEST-06 done; corpus moved out of `spike/inputs/` to `~/.config/policycodex/corpus/pt/` (gitignored, local-only, matches the credentials convention); new corpus-gated integration test `ingest/tests/test_corpus_integration.py` (4 tests, `POLICYCODEX_CORPUS_DIR`-gated, skip in CI); real-corpus run = 19/19 PDFs walked and extracted to non-empty text, manifest built with 19 hashed entries, incremental first-run added=19 then second-run unchanged=19 / to_process=0; no product code changed. Match the file's existing entry style.

- [ ] **Step 3: Mark INGEST-06 done in the sprint board**

In `PolicyWonk-v0.1-Tickets.md`, update the INGEST-06 row to the project's "done" convention (match how the other completed tickets in that file are marked — check a recently-closed ticket like INGEST-05 for the exact format before editing).

- [ ] **Step 4: Update the CLAUDE.md status line**

In `CLAUDE.md` "Current Status", append an INGEST-06 done note to the Week-5 progress paragraph (date 2026-06-08, the new test, env-var gate, 19/19 result, new suite count) and remove INGEST-06 from the "Remaining" list so only `APP-28 -> APP-29` (plus any other still-open items) remain. Get the new suite count from Step 1 of this task's full-suite run below.

- [ ] **Step 5: Confirm the full suite count for the status note**

Run: `ai/venv/bin/python -m pytest -q`
Expected: all pass; the 4 new corpus tests skipped (env var unset). Record the total collected count (passed + skipped) for the CLAUDE.md status line.

- [ ] **Step 6: Commit**

```bash
git add internal/PolicyWonk-Daily-Log.md PolicyWonk-v0.1-Tickets.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(ingest-06): mark INGEST-06 done, log full PT-corpus ingest run

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:** INGEST-06 = "Test ingest against the v0.1 PT corpus (the 19 spike PDFs) in a local folder." Covered: Task 1 (walk + extract all files), Task 2 (manifest + incremental over the corpus), Task 3 (real 19-PDF run captured as evidence + ticket/status close). The "in a local folder" requirement is met by the `POLICYCODEX_CORPUS_DIR` local path. The "19 PDFs / no larger export" (OQ-08) is verified at run time, not hardcoded, preserving ship-generic.

**Placeholder scan:** No TBDs. Every code step shows complete file content or exact appended blocks. Doc steps (Task 3 Steps 2-4) describe content to write and explicitly point at an existing entry/ticket to match formatting, rather than inventing a format — the existing files are the source of truth and pasting fabricated formatting would be worse.

**Type consistency:** Uses the real public API — `LocalFolderConnector(root).walk()`, `extract(path)`, `build_manifest(paths, source_label=...)`, `plan_incremental_run(root, manifest_path, source_label=...)`, `save_manifest(entries, path)`, and `ManifestDiff.added/.changed/.unchanged/.removed/.to_process/.current`. All verified against the current source in `ingest/`. `ManifestEntry.content_hash` is a 64-char SHA-256 hex digest (confirmed: `hashlib.sha256().hexdigest()`).

**Scope guard:** No new production code; no AI/network calls; no PT specifics or absolute paths in committed test code. If verification reveals a missing convenience orchestrator (a single "ingest folder -> texts + manifest" entry point), that is a *new feature* and belongs in a separate ticket, not this verification pass.
