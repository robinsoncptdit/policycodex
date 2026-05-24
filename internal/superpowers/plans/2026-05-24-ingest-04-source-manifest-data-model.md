# INGEST-04 Source Manifest Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure data model for the ingest source manifest — one entry per source file capturing path, content hash, last-modified time, and source label — so the inventory pass can record what it ingested and INGEST-05 can later skip unchanged files.

**Architecture:** A frozen dataclass `ManifestEntry` plus three module functions in a new `ingest/manifest.py`: `entry_for(path, source_label)` (reads a file, computes its SHA-256, captures mtime), `build_manifest(paths, source_label)` (maps `entry_for` over an iterable, sorted by path for stable output), and `to_dict`/`from_dict` round-trip helpers so a manifest can be serialized for INGEST-05's incremental comparison. No persistence, no CLI, no connector wiring in this ticket (YAGNI — those are INGEST-05/AI-10).

**Tech Stack:** Python 3.14 stdlib only (`dataclasses`, `hashlib`, `pathlib`), pytest. Interpreter: `ai/venv/bin/python`.

---

## Scope notes (read before starting)

- Ticket INGEST-04: "Source manifest data model (path, hash, last-modified, source label). Pure data model + tests; sets up INGEST-05 incremental re-runs."
- Lane acceptance (Week 4) context: re-running ingest against the same directory with one file changed must re-process only the changed file. That comparison is INGEST-05's job; INGEST-04 only supplies the model and the hash that makes the comparison possible. Hash is the change-detection key, so it must be content-based and deterministic.
- Pairs with `ingest/local_folder.py:LocalFolderConnector.walk()` which yields `Path` objects; `build_manifest` consumes exactly that iterable. Do not couple the two in this ticket — `build_manifest` takes any `Iterable[Path]`.
- Hash choice: SHA-256, hex digest, read in 64 KiB chunks (the v0.1 corpus is 19 PDFs, some multi-MB; chunked read avoids loading whole files into memory).
- `last_modified` is `float` (`st_mtime`) — raw and serialization-friendly. Do not convert to `datetime` (adds tz ambiguity for no benefit; INGEST-05 compares hashes, not times).

## File Structure

- Create: `ingest/manifest.py` — `ManifestEntry` dataclass + `entry_for`, `build_manifest`, `to_dict`, `from_dict`.
- Create: `ingest/tests/test_manifest.py` — unit tests.
- No other files change.

---

### Task 1: `ManifestEntry` dataclass + `entry_for`

**Files:**
- Create: `ingest/manifest.py`
- Test: `ingest/tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ingest.manifest (INGEST-04: source manifest data model)."""
import hashlib

import pytest

from ingest.manifest import ManifestEntry, entry_for


def test_entry_for_captures_path_hash_mtime_label(tmp_path):
    f = tmp_path / "policy.txt"
    f.write_bytes(b"hello world")
    entry = entry_for(f, source_label="local-folder")

    assert entry.path == f
    assert entry.content_hash == hashlib.sha256(b"hello world").hexdigest()
    assert entry.last_modified == f.stat().st_mtime
    assert entry.source_label == "local-folder"


def test_entry_for_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        entry_for(tmp_path / "nope.pdf", source_label="local-folder")


def test_manifest_entry_is_frozen(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"x")
    entry = entry_for(f, source_label="local-folder")
    with pytest.raises(Exception):
        entry.content_hash = "tampered"  # frozen dataclass rejects mutation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingest.manifest'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Source manifest data model for the ingest pipeline.

One ``ManifestEntry`` per ingested source file records its path, a
content hash, the file's last-modified time, and a label naming where it
came from. The content hash is the change-detection key: INGEST-05 compares
a stored manifest against a freshly built one and re-processes only the
files whose hash changed.

This module is pure data + hashing. It does no persistence, no directory
walking (that is ``ingest/local_folder.py``), and no connector wiring.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_HASH_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class ManifestEntry:
    """One source file's manifest record.

    Attributes:
        path: Filesystem path to the source file.
        content_hash: SHA-256 hex digest of the file's bytes.
        last_modified: The file's ``st_mtime`` (seconds since epoch).
        source_label: Label identifying the ingest source (e.g. "local-folder").
    """

    path: Path
    content_hash: str
    last_modified: float
    source_label: str


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry_for(path: Path, source_label: str) -> ManifestEntry:
    """Build a ManifestEntry for a single existing file.

    Raises FileNotFoundError if the path does not exist.
    """
    path = Path(path)
    stat = path.stat()  # raises FileNotFoundError if missing
    return ManifestEntry(
        path=path,
        content_hash=_hash_file(path),
        last_modified=stat.st_mtime,
        source_label=source_label,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add ingest/manifest.py ingest/tests/test_manifest.py
git commit -m "feat(INGEST-04): ManifestEntry dataclass + entry_for"
```

---

### Task 2: `build_manifest` over an iterable of paths

**Files:**
- Modify: `ingest/manifest.py`
- Test: `ingest/tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
from ingest.manifest import build_manifest


def test_build_manifest_one_entry_per_path_sorted(tmp_path):
    (tmp_path / "b.txt").write_bytes(b"bbb")
    (tmp_path / "a.txt").write_bytes(b"aaa")
    paths = [tmp_path / "b.txt", tmp_path / "a.txt"]

    manifest = build_manifest(paths, source_label="local-folder")

    assert len(manifest) == 2
    # Sorted by path for deterministic, diff-stable output.
    assert [e.path.name for e in manifest] == ["a.txt", "b.txt"]
    assert all(e.source_label == "local-folder" for e in manifest)


def test_build_manifest_empty_iterable_returns_empty_list(tmp_path):
    assert build_manifest([], source_label="local-folder") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py::test_build_manifest_one_entry_per_path_sorted -v`
Expected: FAIL with `ImportError: cannot import name 'build_manifest'`

- [ ] **Step 3: Write minimal implementation** (append to `ingest/manifest.py`)

```python
def build_manifest(
    paths: Iterable[Path], source_label: str
) -> list[ManifestEntry]:
    """Build a manifest for every path in ``paths``.

    Entries are sorted by path so the output is deterministic regardless of
    iteration order, keeping serialized-manifest diffs stable.
    """
    entries = [entry_for(p, source_label) for p in paths]
    return sorted(entries, key=lambda e: str(e.path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add ingest/manifest.py ingest/tests/test_manifest.py
git commit -m "feat(INGEST-04): build_manifest over an iterable of paths"
```

---

### Task 3: `to_dict` / `from_dict` serialization round-trip

**Files:**
- Modify: `ingest/manifest.py`
- Test: `ingest/tests/test_manifest.py`

Rationale: INGEST-05 must persist a manifest and compare it to a fresh one. A plain-dict round-trip (JSON/YAML-friendly) is the minimal serialization surface; file persistence stays in INGEST-05.

- [ ] **Step 1: Write the failing test**

```python
from ingest.manifest import to_dict, from_dict


def test_to_dict_from_dict_round_trip(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"PDF-bytes")
    entry = entry_for(f, source_label="local-folder")

    d = to_dict(entry)
    assert d == {
        "path": str(f),
        "content_hash": entry.content_hash,
        "last_modified": entry.last_modified,
        "source_label": "local-folder",
    }

    restored = from_dict(d)
    assert restored == entry  # frozen dataclass equality, Path == Path


def test_from_dict_coerces_path_string(tmp_path):
    d = {
        "path": str(tmp_path / "x.txt"),
        "content_hash": "abc",
        "last_modified": 1.0,
        "source_label": "local-folder",
    }
    entry = from_dict(d)
    from pathlib import Path as _P
    assert isinstance(entry.path, _P)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py::test_to_dict_from_dict_round_trip -v`
Expected: FAIL with `ImportError: cannot import name 'to_dict'`

- [ ] **Step 3: Write minimal implementation** (append to `ingest/manifest.py`)

```python
def to_dict(entry: ManifestEntry) -> dict[str, Any]:
    """Serialize a ManifestEntry to a plain JSON/YAML-friendly dict.

    ``path`` is stored as a string so the dict survives JSON/YAML round-trips.
    """
    return {
        "path": str(entry.path),
        "content_hash": entry.content_hash,
        "last_modified": entry.last_modified,
        "source_label": entry.source_label,
    }


def from_dict(data: dict[str, Any]) -> ManifestEntry:
    """Rebuild a ManifestEntry from a dict produced by ``to_dict``."""
    return ManifestEntry(
        path=Path(data["path"]),
        content_hash=data["content_hash"],
        last_modified=data["last_modified"],
        source_label=data["source_label"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ingest/tests/test_manifest.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add ingest/manifest.py ingest/tests/test_manifest.py
git commit -m "feat(INGEST-04): to_dict/from_dict manifest serialization round-trip"
```

---

### Task 4: Full-suite verification

- [ ] **Step 1: Run the whole suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: `329 passed` (322 baseline + 7 new).

---

## Self-Review checklist (run before requesting review)

- All four required fields present: path, content hash, last-modified, source label. ✔
- Hash is content-based + deterministic, enabling INGEST-05 change detection. ✔
- Serialization round-trip supports INGEST-05 persistence without building it here. ✔
- No directory walking / no CLI / no connector coupling — stays a pure data model. ✔
- No placeholders; every step has runnable code/commands. ✔
- Names consistent across tasks (`ManifestEntry`, `entry_for`, `build_manifest`, `to_dict`, `from_dict`, `content_hash`, `last_modified`, `source_label`). ✔

## Dispatch note

Implementer runs in `isolation: "worktree"`, Sonnet. First action inside the worktree: `git merge main` into the auto-branch. Critical Operational Note applies: never `cd /Users/chuck/PolicyWonk` for git ops; operate only inside the worktree. Two-stage review (spec then quality) before merge.
