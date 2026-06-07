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


from ingest.incremental import plan_incremental_run


def test_incremental_rerun_processes_only_changed_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    (src / "b.txt").write_text("bravo")
    manifest_path = tmp_path / "manifest.json"

    # First run: no prior manifest -> both files are new.
    first = plan_incremental_run(src, manifest_path)
    assert sorted(e.path.name for e in first.to_process) == ["a.txt", "b.txt"]
    save_manifest(first.current, manifest_path)  # caller persists after processing

    # Edit exactly one file.
    (src / "b.txt").write_text("bravo-EDITED")

    second = plan_incremental_run(src, manifest_path)
    assert [e.path.name for e in second.to_process] == ["b.txt"]
    assert [e.path.name for e in second.unchanged] == ["a.txt"]


def test_incremental_rerun_no_changes_processes_nothing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    manifest_path = tmp_path / "manifest.json"

    first = plan_incremental_run(src, manifest_path)
    save_manifest(first.current, manifest_path)

    second = plan_incremental_run(src, manifest_path)
    assert second.to_process == []
    assert [e.path.name for e in second.unchanged] == ["a.txt"]
