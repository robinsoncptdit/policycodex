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
