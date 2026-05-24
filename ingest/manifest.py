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
