"""Tests for the vendored foundational-policy CI guard.

The guard script lives at repo-template/.github/scripts/foundational_guard.py
and is copied verbatim into a diocese policy repo, so it must stay
standalone. We load it by path here rather than importing a package.
"""
import importlib.util
import subprocess
from pathlib import Path

import yaml

_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "foundational_guard.py"
)
_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "foundational-guard.yml"
)


def _load_guard():
    import sys
    spec = importlib.util.spec_from_file_location("foundational_guard", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["foundational_guard"] = mod  # required: @dataclass __module__ resolution on Python 3.14+
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def test_parse_frontmatter_reads_mapping():
    text = "---\nfoundational: true\nprovides:\n  - classifications\n---\nbody\n"
    fm = guard.parse_frontmatter(text)
    assert fm["foundational"] is True
    assert fm["provides"] == ["classifications"]


def test_parse_frontmatter_none_returns_empty():
    assert guard.parse_frontmatter(None) == {}


def test_parse_frontmatter_no_block_returns_empty():
    assert guard.parse_frontmatter("# just a heading\n") == {}


def test_is_foundational_and_provides_of():
    assert guard.is_foundational({"foundational": True}) is True
    assert guard.is_foundational({"foundational": False}) is False
    assert guard.is_foundational({}) is False
    assert guard.provides_of({"provides": ["a", "b"]}) == ["a", "b"]
    assert guard.provides_of({"provides": None}) == []
    assert guard.provides_of({}) == []


def _change(path, change_type, base_fm=None, head_fm=None):
    return guard.Change(
        path=path,
        change_type=change_type,
        base_frontmatter=base_fm or {},
        head_frontmatter=head_fm or {},
    )


def test_deleting_foundational_file_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "deleted",
                       base_fm={"foundational": True, "provides": ["classifications"]})]
    assert len(guard.find_violations(changes)) == 1


def test_deleting_non_foundational_file_is_allowed():
    changes = [_change("policies/code-of-conduct.md", "deleted",
                       base_fm={"title": "Code of Conduct"})]
    assert guard.find_violations(changes) == []


def test_emptying_provides_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications", "retention-schedule"]},
                       head_fm={"foundational": True, "provides": []})]
    assert len(guard.find_violations(changes)) == 1


def test_removing_provides_key_is_a_violation():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True})]
    assert len(guard.find_violations(changes)) == 1


def test_modifying_foundational_without_touching_provides_is_allowed():
    changes = [_change("policies/document-retention/policy.md", "modified",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_adding_foundational_file_is_allowed():
    changes = [_change("policies/new-foundation/policy.md", "added",
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_renaming_foundational_file_is_allowed():
    changes = [_change("policies/renamed/policy.md", "renamed",
                       base_fm={"foundational": True, "provides": ["classifications"]},
                       head_fm={"foundational": True, "provides": ["classifications"]})]
    assert guard.find_violations(changes) == []


def test_modifying_non_foundational_is_allowed():
    changes = [_change("policies/code-of-conduct.md", "modified",
                       base_fm={"title": "x"}, head_fm={"title": "y"})]
    assert guard.find_violations(changes) == []


def test_multiple_violations_aggregate():
    changes = [
        _change("policies/a/policy.md", "deleted",
                base_fm={"foundational": True, "provides": ["x"]}),
        _change("policies/b/policy.md", "modified",
                base_fm={"foundational": True, "provides": ["y"]},
                head_fm={"foundational": True, "provides": []}),
    ]
    assert len(guard.find_violations(changes)) == 2


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _run(["git", "init", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "t@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    return tmp_path


def _commit_all(tmp_path, msg):
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", msg], tmp_path)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          check=True, capture_output=True, text=True).stdout.strip()


_FOUNDATIONAL_MD = (
    "---\nfoundational: true\nprovides:\n  - classifications\n---\n"
    "Retention policy body.\n"
)


def test_integration_deleting_foundational_blocks(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    base = _commit_all(repo, "add foundational policy")
    (bundle / "policy.md").unlink()
    head = _commit_all(repo, "delete foundational policy")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 1


def test_integration_deleting_ordinary_policy_passes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    (repo / "policies").mkdir()
    (repo / "policies" / "code-of-conduct.md").write_text(
        "---\ntitle: Code of Conduct\n---\nBody.\n", encoding="utf-8")
    base = _commit_all(repo, "add ordinary policy")
    (repo / "policies" / "code-of-conduct.md").unlink()
    head = _commit_all(repo, "delete ordinary policy")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 0


def test_integration_emptying_provides_blocks(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    base = _commit_all(repo, "add foundational policy")
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: []\n---\nRetention policy body.\n",
        encoding="utf-8")
    head = _commit_all(repo, "empty provides")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 1


def test_integration_missing_env_returns_2(monkeypatch):
    monkeypatch.delenv("BASE_SHA", raising=False)
    monkeypatch.delenv("HEAD_SHA", raising=False)
    assert guard.main() == 2


def test_workflow_triggers_on_pull_request_and_manual_dispatch():
    # The guard still fires on PRs touching policies/**, and REPO-12 adds a
    # manual trigger so a maintainer can re-run it after a workflow-only
    # fix-forward that the path filter would otherwise miss:
    #   gh workflow run foundational-guard.yml --ref main
    wf = yaml.safe_load(_WORKFLOW.read_text())
    # PyYAML parses the bare `on:` key as boolean True.
    on = wf.get("on", wf.get(True))
    assert on["pull_request"]["branches"] == ["main"]
    assert "policies/**" in on["pull_request"]["paths"]
    assert "workflow_dispatch" in on
