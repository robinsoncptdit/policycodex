# INGEST-01 Local Folder Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `LocalFolderConnector` class that walks a directory recursively and yields regular files, with defined skip rules and clear error messages for missing/empty/not-a-directory inputs. Feeds the rest of the ingest pipeline (INGEST-02 connector interface, INGEST-03 content extraction, INGEST-04 manifest model).

**Architecture:** Stdlib only (`pathlib`, `os`). Class-shaped from the start so INGEST-02 can extract an ABC later without breaking callers. Yields `Path` objects via `.walk() -> Iterator[Path]`. Skip rules: hidden entries (any path segment starting with `.`) and symlinks (do not follow). Error cases: missing root → `FileNotFoundError`, non-dir root → `NotADirectoryError`, empty root (no yielded files) → `RuntimeError`. CLI surface: `python -m ingest.local_folder <path>` prints yielded paths one per line.

**Tech Stack:** Python 3.12 stdlib (pathlib, os, argparse), pytest.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` INGEST-01. PRD section P0.1 (`PolicyWonk-v0.1-Spec.md:81-90`) — local folder ingest, recursive walk, lane acceptance includes "fails with a clear error naming the offending path" for missing/empty.

**File-filtering decision (confirmed):** yield ALL non-hidden regular files regardless of extension. Format filtering is INGEST-03's responsibility.

---

## File Structure

- Create: `ingest/__init__.py` — empty.
- Create: `ingest/local_folder.py` — `LocalFolderConnector` class + `__main__` block.
- Create: `ingest/tests/__init__.py` — empty.
- Create: `ingest/tests/test_local_folder.py` — pytest using `tmp_path`.

No new pip deps. No changes to existing `app/`, `ai/`, `spike/`, `core/` code.

---

## Task 1: Package scaffold + happy-path walk

**Files:** Create `ingest/__init__.py`, `ingest/local_folder.py`, `ingest/tests/__init__.py`, `ingest/tests/test_local_folder.py`.

- [ ] **Step 1: Write the failing tests:**

Create `ingest/tests/test_local_folder.py`:

```python
"""Tests for LocalFolderConnector."""
from pathlib import Path

import pytest

from ingest.local_folder import LocalFolderConnector


def test_walk_yields_files_in_flat_dir(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "c.docx").write_bytes(b"docx")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["a.txt", "b.pdf", "c.docx"]


def test_walk_recurses_into_subdirs(tmp_path):
    (tmp_path / "top.md").write_text("top")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "mid.md").write_text("mid")
    deep = sub / "deeper"
    deep.mkdir()
    (deep / "low.md").write_text("low")
    result = sorted(p.relative_to(tmp_path).as_posix() for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["sub/deeper/low.md", "sub/mid.md", "top.md"]
```

- [ ] **Step 2: Verify the tests fail.**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
python -m pytest ingest/tests/test_local_folder.py -v
```

Expected: ImportError, both fail.

- [ ] **Step 3: Implement the scaffold.**

Create `ingest/__init__.py` (empty).
Create `ingest/tests/__init__.py` (empty).
Create `ingest/local_folder.py`:

```python
"""Local-folder file walker for the ingest pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator


class LocalFolderConnector:
    """Walks a local directory recursively, yielding regular files.

    Skip rules: hidden entries (any path segment starting with '.')
    and symlinks (do not follow). Error rules raise with the offending
    path in the message: missing root -> FileNotFoundError; non-dir
    root -> NotADirectoryError; empty root -> RuntimeError.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def walk(self) -> Iterator[Path]:
        for entry in sorted(self._root.rglob("*")):
            if not entry.is_file():
                continue
            yield entry
```

- [ ] **Step 4: Verify tests pass.**

- [ ] **Step 5: Commit:**

```bash
git add ingest/__init__.py ingest/local_folder.py ingest/tests/__init__.py ingest/tests/test_local_folder.py
git commit -m "feat(INGEST-01): LocalFolderConnector with recursive happy-path walk"
```

---

## Task 2: Skip hidden entries

**Files:** Modify `ingest/local_folder.py`, `ingest/tests/test_local_folder.py`.

- [ ] **Step 1: Append failing tests:**

```python
def test_walk_skips_hidden_files(tmp_path):
    (tmp_path / "visible.txt").write_text("v")
    (tmp_path / ".hidden.txt").write_text("h")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["visible.txt"]


def test_walk_skips_files_inside_hidden_dirs(tmp_path):
    (tmp_path / "ok.txt").write_text("ok")
    hidden_dir = tmp_path / ".hidden_dir"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("nope")
    nested_visible = hidden_dir / "visible_inside_hidden.txt"
    nested_visible.write_text("still nope")
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["ok.txt"]
```

- [ ] **Step 2: Verify the first test fails** (the dotfile leaks), and the second fails too (the whole `.hidden_dir/` leaks).

- [ ] **Step 3: Implement skip-hidden.** Update `walk` in `ingest/local_folder.py`:

```python
def walk(self) -> Iterator[Path]:
    for entry in sorted(self._root.rglob("*")):
        if not entry.is_file():
            continue
        relative = entry.relative_to(self._root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        yield entry
```

The check uses `relative.parts` so a hidden ancestor or hidden filename both filter out.

- [ ] **Step 4: Verify all 4 tests pass.**

- [ ] **Step 5: Commit:**

```bash
git add ingest/local_folder.py ingest/tests/test_local_folder.py
git commit -m "feat(INGEST-01): skip hidden files and entries inside hidden dirs"
```

---

## Task 3: Skip symlinks (do not follow)

**Files:** Modify `ingest/local_folder.py`, `ingest/tests/test_local_folder.py`.

- [ ] **Step 1: Append failing test:**

```python
def test_walk_does_not_follow_symlinks(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text("real content")
    link = tmp_path / "link_to_real.txt"
    link.symlink_to(real)
    result = sorted(p.name for p in LocalFolderConnector(tmp_path).walk())
    assert result == ["real.txt"]
```

- [ ] **Step 2: Verify it fails** (the symlink leaks because `is_file()` resolves symlinks by default).

- [ ] **Step 3: Implement symlink skip.** Update `walk`:

```python
def walk(self) -> Iterator[Path]:
    for entry in sorted(self._root.rglob("*")):
        if entry.is_symlink():
            continue
        if not entry.is_file():
            continue
        relative = entry.relative_to(self._root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        yield entry
```

The symlink check comes first so it applies to both file-symlinks and dir-symlinks (and `rglob` won't descend a dir-symlink that we explicitly skip).

- [ ] **Step 4: Verify all 5 tests pass.**

- [ ] **Step 5: Commit:**

```bash
git add ingest/local_folder.py ingest/tests/test_local_folder.py
git commit -m "feat(INGEST-01): do not follow symlinks"
```

---

## Task 4: Error cases (missing / not-a-dir / empty)

**Files:** Modify `ingest/local_folder.py`, `ingest/tests/test_local_folder.py`.

- [ ] **Step 1: Append failing tests:**

```python
def test_walk_raises_filenotfound_on_missing_root(tmp_path):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        list(LocalFolderConnector(missing).walk())


def test_walk_raises_notadirectory_on_file_root(tmp_path):
    f = tmp_path / "iam_a_file.txt"
    f.write_text("x")
    with pytest.raises(NotADirectoryError, match=str(f)):
        list(LocalFolderConnector(f).walk())


def test_walk_raises_runtimeerror_on_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match=str(empty)):
        list(LocalFolderConnector(empty).walk())


def test_walk_raises_runtimeerror_when_only_hidden_entries(tmp_path):
    """A dir that yields zero non-hidden files is treated as empty per the spec."""
    only_hidden = tmp_path / "only_hidden"
    only_hidden.mkdir()
    (only_hidden / ".dotfile").write_text("h")
    with pytest.raises(RuntimeError, match=str(only_hidden)):
        list(LocalFolderConnector(only_hidden).walk())
```

- [ ] **Step 2: Verify all 4 new tests fail.**

- [ ] **Step 3: Implement error cases.** Replace `walk`:

```python
def walk(self) -> Iterator[Path]:
    if not self._root.exists():
        raise FileNotFoundError(f"Source folder does not exist: {self._root}")
    if not self._root.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {self._root}")
    yielded = 0
    for entry in sorted(self._root.rglob("*")):
        if entry.is_symlink():
            continue
        if not entry.is_file():
            continue
        relative = entry.relative_to(self._root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        yielded += 1
        yield entry
    if yielded == 0:
        raise RuntimeError(f"Source folder contains no files: {self._root}")
```

Note: the post-walk `RuntimeError` raises AFTER the generator has yielded zero items; callers materializing the iterator (e.g. `list(...)`) will see the raise. Callers iterating lazily will see yielded files first, then the raise at exhaustion — which is the correct behavior under the "fails with a clear error" rule.

- [ ] **Step 4: Verify all 9 tests pass.**

- [ ] **Step 5: Commit:**

```bash
git add ingest/local_folder.py ingest/tests/test_local_folder.py
git commit -m "feat(INGEST-01): raise on missing / non-dir / empty source folder"
```

---

## Task 5: CLI surface

**Files:** Modify `ingest/local_folder.py`.

- [ ] **Step 1: Add `__main__` block** at the end of `ingest/local_folder.py`:

```python
def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Walk a local folder and print regular non-hidden file paths."
    )
    parser.add_argument("path", help="Directory to walk recursively.")
    args = parser.parse_args(argv)
    connector = LocalFolderConnector(Path(args.path))
    for p in connector.walk():
        print(p)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test the CLI** against the spike inputs:

```bash
python -m ingest.local_folder spike/inputs | head -5 ; echo "---"
python -m ingest.local_folder spike/inputs | wc -l
```

Expected: 5 PDF paths on stdout, total ≥18 lines (19 spike PDFs minus any hidden, which there are none of). Exit 0.

Also smoke-test the error path:

```bash
python -m ingest.local_folder /nonexistent ; echo "exit=$?"
```

Expected: prints the `FileNotFoundError` traceback to stderr, exits non-zero.

- [ ] **Step 3: Verify all tests still pass:**

```bash
python -m pytest ingest/ -v
```

- [ ] **Step 4: Commit:**

```bash
git add ingest/local_folder.py
git commit -m "feat(INGEST-01): CLI entry point via python -m ingest.local_folder"
```

---

## Definition of Done (paste output in report)

1. `python -m pytest ingest/ -v` — all 9 tests pass.
2. `python -m ingest.local_folder spike/inputs | wc -l` — returns ≥18 (matches the count of non-hidden files in `spike/inputs/`).
3. `python -m ingest.local_folder /nonexistent ; echo $?` — non-zero exit, error message names `/nonexistent`.
4. No changes outside `ingest/`.
5. No new pip dependencies.

## Report format

```
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

Worktree: <path>
Branch: <name>

Commits (oldest to newest):
- <sha> <subject>
- ...

Verification:
$ python -m pytest ingest/ -v
<paste>

$ python -m ingest.local_folder spike/inputs | head -3
<paste>

$ python -m ingest.local_folder spike/inputs | wc -l
<paste>

$ python -m ingest.local_folder /nonexistent ; echo "exit=$?"
<paste>

Files changed:
- <path>
- ...

Concerns / open questions:
- ...
```

If you hit BLOCKED or NEEDS_CONTEXT before completing, stop and report immediately. Do not modify files outside `ingest/`.
