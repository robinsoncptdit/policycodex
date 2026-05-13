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
        for entry in sorted(self._root.rglob("*")):
            if entry.is_symlink():
                continue
            if not entry.is_file():
                continue
            relative = entry.relative_to(self._root)
            if any(part.startswith(".") for part in relative.parts):
                continue
            yield entry
