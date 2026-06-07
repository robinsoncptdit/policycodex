"""Tests for ingest.manifest (INGEST-04: source manifest data model)."""
import dataclasses
import hashlib
from pathlib import Path

import pytest

from ingest.manifest import (
    ManifestEntry,
    build_manifest,
    entry_for,
    from_dict,
    to_dict,
)


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
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.content_hash = "tampered"  # frozen dataclass rejects mutation


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
    assert isinstance(entry.path, Path)
    assert entry.path == Path(d["path"])


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
