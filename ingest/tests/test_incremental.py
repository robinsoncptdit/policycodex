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
