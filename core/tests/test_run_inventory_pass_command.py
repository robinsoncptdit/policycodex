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

    class FakeConnector:
        def __init__(self, root):
            self.root = root

        def walk(self):
            return iter(files)

    monkeypatch.setattr(cmd, "LocalFolderConnector", FakeConnector)
    monkeypatch.setattr(cmd, "build_manifest", lambda paths, label: list(paths))
    return SimpleNamespace(work=work, files=files, config=config)


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
    assert len(captured["manifest"]) == 2
