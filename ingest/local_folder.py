"""Local-folder file walker for the ingest pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator


class LocalFolderConnector:
    """Walks a local directory recursively, yielding regular files.

    Skip rules: hidden entries (any path segment starting with '.')
    and symlinks (do not follow). Error rules: missing root ->
    FileNotFoundError; non-dir root -> NotADirectoryError; empty root
    (no yielded files) -> RuntimeError.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

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
