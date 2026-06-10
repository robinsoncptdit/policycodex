"""Wiring tests for the run_inventory_pass management command (AI-10).

The orchestrator itself is tested in ai/tests/test_inventory.py; here we only
assert the Django-side wiring: taxonomy presence is enforced, and the loaded
manifest + taxonomy + config are handed to run_inventory_pass.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

import core.management.commands.run_inventory_pass as cmd
from ai.inventory import InventoryResult


@pytest.fixture
def patched(monkeypatch, tmp_path):
    work = tmp_path / "work"
    (work / "policies").mkdir(parents=True)
    config = SimpleNamespace(working_dir=work, branch="main")
    monkeypatch.setattr(cmd, "load_working_copy_config", lambda: config)
    monkeypatch.setattr(cmd, "GitHubProvider", lambda: "GITHUB")
    monkeypatch.setattr(cmd, "ClaudeProvider", lambda: "CLAUDE")

    files = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    for f in files:
        f.write_text("x", encoding="utf-8")

    # AI-17: default the incremental plan to a no-op diff in which everything is
    # NEW (added=files, changed=[], etc). Mirrors the pre-AI-17 happy-path
    # behavior so the existing `test_happy_path_calls_orchestrator_with_loaded_inputs`
    # assertion `len(captured["manifest"]) == 2` still holds.
    default_diff = SimpleNamespace(
        added=files, changed=[], unchanged=[], removed=[],
        current=files, to_process=files,
    )
    monkeypatch.setattr(
        cmd, "plan_incremental_run",
        lambda root, manifest_path, source_label: default_diff,
    )
    # AI-17: never touch the filesystem from the default fixture; tests that
    # care about persistence reset this with their own patch.
    saved = []
    monkeypatch.setattr(
        cmd, "save_manifest",
        lambda entries, path: saved.append((list(entries), path)),
    )
    return SimpleNamespace(
        work=work, files=files, config=config, default_diff=default_diff,
        saved=saved,
    )


def test_errors_when_no_foundational_bundle(monkeypatch, patched, tmp_path):
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: None)
    with pytest.raises(CommandError, match="foundational"):
        call_command("run_inventory_pass", str(tmp_path))


def test_happy_path_calls_orchestrator_with_loaded_inputs(monkeypatch, patched, tmp_path):
    taxonomy = {"classifications": [], "retention_schedule": []}
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: taxonomy)

    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return InventoryResult(written=["a", "b"], pr={"url": "https://example/pr/9"})

    monkeypatch.setattr(cmd, "run_inventory_pass", fake_run)
    call_command("run_inventory_pass", str(tmp_path))

    assert captured["taxonomy"] is taxonomy
    assert captured["base_branch"] == "main"
    assert captured["provider"] == "GITHUB"
    assert captured["llm_provider"] == "CLAUDE"
    assert captured["author_name"] == "PolicyCodex"
    # AI-17: orchestrator now receives diff.added as manifest, diff.changed
    # as changed_entries. The default fixture's diff has added=files, changed=[].
    assert len(captured["manifest"]) == 2
    assert captured["changed_entries"] == []
    # Default fixture persists the manifest after a successful run.
    assert len(patched.saved) == 1
    saved_entries, saved_path = patched.saved[0]
    assert saved_entries == patched.files  # diff.current


# AI-17: end-to-end command -> incremental -> orchestrator wiring.

def test_command_passes_diff_added_and_changed_to_orchestrator(monkeypatch, patched, tmp_path):
    """A diff with added=[a] and changed=[b] threads through cleanly: the
    orchestrator's manifest receives only [a], and changed_entries receives [b]."""
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: {"x": 1})

    file_a, file_b = patched.files
    diff = SimpleNamespace(
        added=[file_a], changed=[file_b], unchanged=[], removed=[],
        current=[file_a, file_b], to_process=[file_a, file_b],
    )
    monkeypatch.setattr(
        cmd, "plan_incremental_run",
        lambda root, manifest_path, source_label: diff,
    )

    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return InventoryResult(written=["a"], skipped_changed=["b"])

    monkeypatch.setattr(cmd, "run_inventory_pass", fake_run)
    call_command("run_inventory_pass", str(tmp_path))

    assert captured["manifest"] == [file_a]
    assert captured["changed_entries"] == [file_b]
    # save_manifest called once with diff.current.
    assert len(patched.saved) == 1
    saved_entries, _saved_path = patched.saved[0]
    assert saved_entries == [file_a, file_b]


def test_command_does_not_persist_manifest_when_orchestrator_raises(monkeypatch, patched, tmp_path):
    """Crash-safe persistence: if run_inventory_pass raises, save_manifest is
    never called (next run re-diffs against the prior manifest)."""
    monkeypatch.setattr(cmd, "load_foundational_taxonomy", lambda d, r: {"x": 1})

    def boom(**kwargs):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(cmd, "run_inventory_pass", boom)

    with pytest.raises(RuntimeError, match="simulated"):
        call_command("run_inventory_pass", str(tmp_path))

    # Crash-safe: the default fixture's save_manifest never runs.
    assert patched.saved == []
