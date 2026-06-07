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
