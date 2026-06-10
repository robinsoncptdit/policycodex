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


# REPO-14: extend the guard to inspect data.yaml diffs and fail any
# classification id removed without a `deprecated: true` tombstone.

def _data_yaml_change(path, change_type, base_data=None, head_data=None):
    return guard.DataYamlChange(
        path=path,
        change_type=change_type,
        base_data=base_data or {},
        head_data=head_data or {},
    )


def test_data_yaml_change_dataclass_is_frozen():
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data={"x": 1}, head_data={"x": 2})
    import dataclasses
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        ch.path = "policies/other/data.yaml"


def test_parse_data_yaml_handles_missing_text():
    assert guard._parse_data_yaml(None) == {}
    assert guard._parse_data_yaml("") == {}


def test_parse_data_yaml_handles_unparseable():
    assert guard._parse_data_yaml("- not a mapping\n") == {}
    assert guard._parse_data_yaml(":\n:\n:\n") == {}


def test_data_yaml_unchanged_classifications_pass():
    base = {"classifications": [{"id": "administrative", "name": "Administrative"}]}
    head = {"classifications": [{"id": "administrative", "name": "Administrative Records"}]}
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data=base, head_data=head)
    assert guard.find_data_yaml_violations([ch]) == []


def test_data_yaml_added_classification_passes():
    base = {"classifications": [{"id": "administrative", "name": "Administrative"}]}
    head = {"classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ]}
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data=base, head_data=head)
    assert guard.find_data_yaml_violations([ch]) == []


def test_data_yaml_soft_delete_passes():
    """Id stays in head with deprecated:true -> no violation."""
    base = {"classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "legacy-hr", "name": "Legacy HR Records"},
    ]}
    head = {"classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "legacy-hr", "name": "Legacy HR Records", "deprecated": True},
    ]}
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data=base, head_data=head)
    assert guard.find_data_yaml_violations([ch]) == []


def test_data_yaml_hard_remove_active_id_violates():
    """Id removed entirely from head -> violation, with the id named in the message."""
    base = {"classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ]}
    head = {"classifications": [{"id": "administrative", "name": "Administrative"}]}
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data=base, head_data=head)
    violations = guard.find_data_yaml_violations([ch])
    assert len(violations) == 1
    assert "financial" in violations[0]
    assert "deprecated: true" in violations[0]


def test_data_yaml_hard_remove_already_deprecated_id_still_violates():
    """Even an already-deprecated id cannot be hard-removed via PR."""
    base = {"classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "legacy-hr", "name": "Legacy HR Records", "deprecated": True},
    ]}
    head = {"classifications": [{"id": "administrative", "name": "Administrative"}]}
    ch = _data_yaml_change("policies/document-retention/data.yaml", "modified",
                           base_data=base, head_data=head)
    violations = guard.find_data_yaml_violations([ch])
    assert len(violations) == 1
    assert "legacy-hr" in violations[0]


def test_data_yaml_added_or_deleted_change_types_skip():
    """Only `modified` enters the rule; add/delete fall under .md rules."""
    added = _data_yaml_change("policies/new/data.yaml", "added",
                              head_data={"classifications": [{"id": "a", "name": "A"}]})
    deleted = _data_yaml_change("policies/gone/data.yaml", "deleted",
                                base_data={"classifications": [{"id": "a", "name": "A"}]})
    assert guard.find_data_yaml_violations([added, deleted]) == []


def test_integration_data_yaml_remove_classification_blocks(tmp_path, monkeypatch):
    """End-to-end: a real git repo with a data.yaml that hard-removes an id -> main() returns 1."""
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    (bundle / "data.yaml").write_text(
        "classifications:\n"
        "- id: administrative\n"
        "  name: Administrative\n"
        "- id: financial\n"
        "  name: Financial\n",
        encoding="utf-8",
    )
    base = _commit_all(repo, "add foundational bundle with two classifications")
    (bundle / "data.yaml").write_text(
        "classifications:\n"
        "- id: administrative\n"
        "  name: Administrative\n",
        encoding="utf-8",
    )
    head = _commit_all(repo, "hard-remove financial classification")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 1


def test_integration_data_yaml_soft_delete_passes(tmp_path, monkeypatch):
    """End-to-end: a soft-delete (deprecated:true tombstone kept) -> main() returns 0."""
    repo = _init_repo(tmp_path)
    bundle = repo / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(_FOUNDATIONAL_MD, encoding="utf-8")
    (bundle / "data.yaml").write_text(
        "classifications:\n"
        "- id: administrative\n"
        "  name: Administrative\n"
        "- id: financial\n"
        "  name: Financial\n",
        encoding="utf-8",
    )
    base = _commit_all(repo, "add foundational bundle with two classifications")
    (bundle / "data.yaml").write_text(
        "classifications:\n"
        "- id: administrative\n"
        "  name: Administrative\n"
        "- id: financial\n"
        "  name: Financial\n"
        "  deprecated: true\n",
        encoding="utf-8",
    )
    head = _commit_all(repo, "soft-delete financial classification")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    assert guard.main() == 0
