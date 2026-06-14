"""F2 (APP-33 on the inventory orchestrator): a git-provider failure during the
bulk-PR step must restore a clean default branch, and success must also leave
the working copy on the default branch (so the next sync pull is not wedged)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ai.inventory import run_inventory_pass
from ai.provider import CompletionResult, Usage
from ingest.manifest import ManifestEntry

_FAKE_USAGE = Usage("fake", "m", 1, 2, "2026-06-08T00:00:00+00:00")


class _FakeLLM:
    def complete(self, prompt, max_tokens):
        return CompletionResult(
            text=json.dumps({
                "title": "Policy", "summary": "s", "category": "IT",
                "category_confidence": "high", "retention_period_years": 7,
                "version_stamp": "1.0",
            }),
            usage=_FAKE_USAGE,
        )


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", cwd=path)
    _git("config", "user.email", "t@t.local", cwd=path)
    _git("config", "user.name", "t", cwd=path)
    (path / "README.md").write_text("seed\n")
    _git("add", "-A", cwd=path)
    _git("commit", "-m", "seed", cwd=path)
    _git("branch", "-M", "main", cwd=path)  # deterministic default branch name


def _current_branch(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=path, capture_output=True, text=True,
    ).stdout.strip()


def _branch_list(path: Path) -> str:
    return subprocess.run(
        ["git", "branch"], cwd=path, capture_output=True, text=True
    ).stdout


def _one_manifest(tmp_path: Path) -> list[ManifestEntry]:
    src = tmp_path / "src.txt"
    src.write_text("Real policy text.", encoding="utf-8")
    return [ManifestEntry(path=src, content_hash="h", last_modified=0.0, source_label="local-folder")]


class _RealGitPushFails:
    """branch/commit run real git; push raises (simulated remote failure)."""

    def branch(self, name, working_dir):
        _git("checkout", "-b", name, cwd=working_dir)

    def commit(self, message, files, author_name, author_email, working_dir):
        for f in files:
            _git("add", str(f), cwd=working_dir)
        _git("-c", f"user.email={author_email}", "-c", f"user.name={author_name}",
             "commit", "-m", message, cwd=working_dir)
        return "sha"

    def push(self, branch, working_dir):
        raise RuntimeError("simulated push failure")

    def open_pr(self, **kwargs):
        raise AssertionError("open_pr must not be reached after push fails")


class _RealGitPushNoop(_RealGitPushFails):
    """push succeeds (no remote); open_pr returns a dict."""

    def push(self, branch, working_dir):
        return None

    def open_pr(self, title, body, head_branch, base_branch, working_dir):
        return {"pr_number": 1, "url": "https://example/pr/1", "state": "open"}


def test_push_failure_restores_default_branch(tmp_path):
    working = tmp_path / "working"
    _init_repo(working)
    with pytest.raises(RuntimeError, match="simulated push failure"):
        run_inventory_pass(
            manifest=_one_manifest(tmp_path),
            working_dir=working,
            provider=_RealGitPushFails(),
            llm_provider=_FakeLLM(),
            taxonomy={"classifications": []},
            author_name="t", author_email="t@t.local",
            base_branch="main",
        )
    assert _current_branch(working) == "main"
    assert "inventory-" not in _branch_list(working)


def test_success_returns_to_default_branch(tmp_path):
    working = tmp_path / "working"
    _init_repo(working)
    result = run_inventory_pass(
        manifest=_one_manifest(tmp_path),
        working_dir=working,
        provider=_RealGitPushNoop(),
        llm_provider=_FakeLLM(),
        taxonomy={"classifications": []},
        author_name="t", author_email="t@t.local",
        base_branch="main",
    )
    assert result.pr == {"pr_number": 1, "url": "https://example/pr/1", "state": "open"}
    assert _current_branch(working) == "main"
    assert "inventory-" not in _branch_list(working)
