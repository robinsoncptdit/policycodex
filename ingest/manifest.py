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


def build_manifest(
    paths: Iterable[Path], source_label: str
) -> list[ManifestEntry]:
    """Build a manifest for every path in ``paths``.

    Entries are sorted by path so the output is deterministic regardless of
    iteration order, keeping serialized-manifest diffs stable.
    """
    entries = [entry_for(p, source_label) for p in paths]
    return sorted(entries, key=lambda e: str(e.path))


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
