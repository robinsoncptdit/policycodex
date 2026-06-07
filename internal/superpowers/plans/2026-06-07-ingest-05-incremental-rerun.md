# INGEST-05 Incremental Re-run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-running ingest against the same folder re-processes only files whose content changed (plus new files), by diffing a stored manifest against the current folder contents.

**Architecture:** Three layers, respecting the existing boundary stated in `ingest/manifest.py` ("pure data + hashing, no persistence, no directory walking"). (1) A pure-data `diff_manifests` + `ManifestDiff` added to `manifest.py`. (2) JSON persistence (`save_manifest`/`load_manifest`) and the walk-build-diff orchestrator (`plan_incremental_run`) in a new `ingest/incremental.py`. The orchestrator deliberately does NOT save — the caller saves the new manifest only after processing succeeds, so a crash mid-run does not poison the next diff into skipping a file.

**Tech Stack:** Python 3.14, stdlib `json`/`hashlib`/`pathlib`, pytest. Test interpreter: `ai/venv/bin/python` (no root venv).

**Scope note (YAGNI):** Deliverable is the library capability + tests. The diff returns `list[ManifestEntry]` (`ManifestDiff.to_process`) that feeds the existing `ai.inventory.run_inventory_pass(manifest=...)` unchanged. No new CLI and no inventory-command rewiring here — that is a separate, trivial follow-on and not needed to satisfy the lane acceptance ("re-running with one file changed re-processes only the changed file").

---

### Task 1: `ManifestDiff` + `diff_manifests` (pure data, in `manifest.py`)

**Files:**
- Modify: `ingest/manifest.py`
- Test: `ingest/tests/test_manifest.py`

- [ ] **Step 1: Write the failing tests**

Append to `ingest/tests/test_manifest.py`:

```python
from ingest.manifest import ManifestDiff, diff_manifests


def _entry(name, h, mtime=1.0, source="local-folder"):
    return ManifestEntry(
        path=Path(name), content_hash=h, last_modified=mtime, source_label=source
    )


def test_diff_classifies_added_changed_unchanged_removed():
    previous = [_entry("a.txt", "h_a"), _entry("b.txt", "h_b"), _entry("c.txt", "h_c")]
    current = [
        _entry("a.txt", "h_a"),       # unchanged
        _entry("b.txt", "h_b_new"),   # changed
        _entry("d.txt", "h_d"),       # added
        # c.txt removed
    ]

    diff = diff_manifests(previous, current)

    assert [e.path.name for e in diff.unchanged] == ["a.txt"]
    assert [e.path.name for e in diff.changed] == ["b.txt"]
    assert [e.path.name for e in diff.added] == ["d.txt"]
    assert [e.path.name for e in diff.removed] == ["c.txt"]
    # changed entry carries the NEW hash, not the prior one
    assert diff.changed[0].content_hash == "h_b_new"


def test_diff_first_run_all_added():
    current = [_entry("a.txt", "h_a"), _entry("b.txt", "h_b")]
    diff = diff_manifests([], current)
    assert [e.path.name for e in diff.added] == ["a.txt", "b.txt"]
    assert diff.changed == [] and diff.unchanged == [] and diff.removed == []


def test_diff_to_process_is_added_plus_changed_sorted():
    previous = [_entry("keep.txt", "h"), _entry("edit.txt", "old")]
    current = [_entry("keep.txt", "h"), _entry("edit.txt", "new"), _entry("brand.txt", "n")]
    diff = diff_manifests(previous, current)
    # added (brand) + changed (edit), sorted by path; unchanged (keep) excluded
    assert [e.path.name for e in diff.to_process] == ["brand.txt", "edit.txt"]


def test_diff_current_excludes_removed():
    previous = [_entry("gone.txt", "h")]
    current = [_entry("here.txt", "h")]
    diff = diff_manifests(previous, current)
    assert [e.path.name for e in diff.current] == ["here.txt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -k diff -v`
Expected: FAIL with `ImportError: cannot import name 'ManifestDiff'` (or `diff_manifests`).

- [ ] **Step 3: Implement `ManifestDiff` + `diff_manifests`**

Add to `ingest/manifest.py` (after the `ManifestEntry` dataclass; `Iterable` and `dataclass` are already imported):

```python
@dataclass(frozen=True)
class ManifestDiff:
    """Classification of a current manifest against a previous one, keyed by path.

    ``added``/``changed``/``unchanged`` hold CURRENT entries; ``removed`` holds
    PRIOR entries (they no longer exist in the current folder).
    """

    added: list[ManifestEntry]
    changed: list[ManifestEntry]
    unchanged: list[ManifestEntry]
    removed: list[ManifestEntry]

    @property
    def to_process(self) -> list[ManifestEntry]:
        """Entries downstream extraction must re-run: new + content-changed."""
        return sorted(self.added + self.changed, key=lambda e: str(e.path))

    @property
    def current(self) -> list[ManifestEntry]:
        """The full current manifest (added + changed + unchanged), to persist after a run."""
        return sorted(
            self.added + self.changed + self.unchanged, key=lambda e: str(e.path)
        )


def diff_manifests(
    previous: Iterable[ManifestEntry], current: Iterable[ManifestEntry]
) -> ManifestDiff:
    """Compare two manifests by path; classify each current/prior file.

    A file is *changed* when its path exists in both but the content hash
    differs; *added* when only in current; *removed* when only in previous;
    *unchanged* otherwise. Pure data: no I/O.
    """
    prev_by_path = {str(e.path): e for e in previous}
    curr_by_path = {str(e.path): e for e in current}

    added: list[ManifestEntry] = []
    changed: list[ManifestEntry] = []
    unchanged: list[ManifestEntry] = []
    for key, entry in curr_by_path.items():
        prior = prev_by_path.get(key)
        if prior is None:
            added.append(entry)
        elif prior.content_hash != entry.content_hash:
            changed.append(entry)
        else:
            unchanged.append(entry)
    removed = [e for key, e in prev_by_path.items() if key not in curr_by_path]

    keyfn = lambda e: str(e.path)  # noqa: E731
    return ManifestDiff(
        added=sorted(added, key=keyfn),
        changed=sorted(changed, key=keyfn),
        unchanged=sorted(unchanged, key=keyfn),
        removed=sorted(removed, key=keyfn),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -k diff -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ingest/manifest.py ingest/tests/test_manifest.py
git commit -m "feat(ingest-05): add ManifestDiff + diff_manifests pure-data comparison"
```

---

### Task 2: Manifest JSON persistence (`save_manifest`/`load_manifest`)

**Files:**
- Create: `ingest/incremental.py`
- Test: `ingest/tests/test_incremental.py`

- [ ] **Step 1: Write the failing tests**

Create `ingest/tests/test_incremental.py`:

```python
"""Tests for ingest.incremental (INGEST-05: incremental re-run support)."""
from pathlib import Path

from ingest.incremental import load_manifest, save_manifest
from ingest.manifest import build_manifest


def test_save_load_manifest_round_trip(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("data")
    entries = build_manifest([f], source_label="local-folder")

    out = tmp_path / "m.json"
    save_manifest(entries, out)
    loaded = load_manifest(out)

    assert loaded == entries  # frozen dataclass equality, Path == Path


def test_load_manifest_missing_returns_empty(tmp_path):
    # First run: no prior manifest on disk -> empty, so everything reads as new.
    assert load_manifest(tmp_path / "nope.json") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_incremental.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingest.incremental'`.

- [ ] **Step 3: Implement persistence in a new module**

Create `ingest/incremental.py`:

```python
"""Incremental re-run support for local-folder ingest (INGEST-05).

Persists a manifest to disk as JSON and, on the next run, diffs the stored
manifest against the current folder so downstream extraction re-processes
only new or content-changed files. Persistence and directory walking live
here; ``ingest/manifest.py`` stays pure data + hashing.
"""
from __future__ import annotations

import json
from pathlib import Path

from ingest.local_folder import LocalFolderConnector
from ingest.manifest import (
    ManifestDiff,
    ManifestEntry,
    build_manifest,
    diff_manifests,
    from_dict,
    to_dict,
)


def save_manifest(entries: list[ManifestEntry], path: Path) -> None:
    """Write a manifest to ``path`` as a JSON array, deterministically."""
    path = Path(path)
    payload = [to_dict(e) for e in entries]
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_manifest(path: Path) -> list[ManifestEntry]:
    """Read a manifest written by ``save_manifest``.

    A missing file returns ``[]`` (a first run has no prior manifest, so the
    diff treats every current file as new).
    """
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(d) for d in data]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_incremental.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ingest/incremental.py ingest/tests/test_incremental.py
git commit -m "feat(ingest-05): add JSON manifest persistence (save/load)"
```

---

### Task 3: `plan_incremental_run` orchestrator + acceptance test

**Files:**
- Modify: `ingest/incremental.py`
- Test: `ingest/tests/test_incremental.py`

- [ ] **Step 1: Write the failing tests**

Append to `ingest/tests/test_incremental.py`:

```python
from ingest.incremental import plan_incremental_run


def test_incremental_rerun_processes_only_changed_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    (src / "b.txt").write_text("bravo")
    manifest_path = tmp_path / "manifest.json"

    # First run: no prior manifest -> both files are new.
    first = plan_incremental_run(src, manifest_path)
    assert sorted(e.path.name for e in first.to_process) == ["a.txt", "b.txt"]
    save_manifest(first.current, manifest_path)  # caller persists after processing

    # Edit exactly one file.
    (src / "b.txt").write_text("bravo-EDITED")

    second = plan_incremental_run(src, manifest_path)
    assert [e.path.name for e in second.to_process] == ["b.txt"]
    assert [e.path.name for e in second.unchanged] == ["a.txt"]


def test_incremental_rerun_no_changes_processes_nothing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    manifest_path = tmp_path / "manifest.json"

    first = plan_incremental_run(src, manifest_path)
    save_manifest(first.current, manifest_path)

    second = plan_incremental_run(src, manifest_path)
    assert second.to_process == []
    assert [e.path.name for e in second.unchanged] == ["a.txt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_incremental.py -k rerun -v`
Expected: FAIL with `ImportError: cannot import name 'plan_incremental_run'`.

- [ ] **Step 3: Implement the orchestrator**

Append to `ingest/incremental.py`:

```python
def plan_incremental_run(
    root: Path,
    manifest_path: Path,
    source_label: str = "local-folder",
) -> ManifestDiff:
    """Walk ``root``, build the current manifest, and diff it against the
    manifest stored at ``manifest_path``.

    Returns the diff; ``diff.to_process`` is the entry list to hand to
    downstream extraction. The caller is responsible for persisting
    ``diff.current`` via ``save_manifest`` AFTER processing succeeds, so a
    crash mid-run does not record unprocessed files as already-seen.
    """
    connector = LocalFolderConnector(Path(root))
    current = build_manifest(connector.walk(), source_label=source_label)
    previous = load_manifest(manifest_path)
    return diff_manifests(previous, current)
```

- [ ] **Step 4: Run the full ingest suite to verify**

Run: `ai/venv/bin/python -m pytest ingest/tests/ -v`
Expected: PASS (all ingest tests, including the new incremental ones).

- [ ] **Step 5: Run the whole suite for regressions**

Run: `ai/venv/bin/python -m pytest -q`
Expected: PASS, count increased by 8 new tests over the prior baseline (493).

- [ ] **Step 6: Commit**

```bash
git add ingest/incremental.py ingest/tests/test_incremental.py
git commit -m "feat(ingest-05): add plan_incremental_run walk-build-diff orchestrator"
```

---

## Self-Review

- **Spec coverage** — Ticket: "Incremental re-run support (skip unchanged files via hash comparison)." Lane acceptance: "Re-running against the same directory with one file changed re-processes only the changed file." Covered by Task 1 (hash diff) + Task 3 (`test_incremental_rerun_processes_only_changed_file`, `test_incremental_rerun_no_changes_processes_nothing`). Missing-folder error behavior is already owned by `LocalFolderConnector` (existing tests) and is reused unchanged.
- **Placeholder scan** — none; every code/test step is complete.
- **Type consistency** — `diff_manifests` / `ManifestDiff` / `.to_process` / `.current` / `save_manifest` / `load_manifest` / `plan_incremental_run` are named and used identically across tasks. `ManifestEntry`, `build_manifest`, `to_dict`, `from_dict` match the existing `ingest/manifest.py` API. Downstream `ai.inventory.run_inventory_pass(manifest=list[ManifestEntry])` accepts `diff.to_process` without adaptation.
- **Architecture boundary** — pure-data diff stays in `manifest.py`; all file I/O and walking live in the new `incremental.py`, honoring `manifest.py`'s stated "no persistence, no directory walking" contract.
