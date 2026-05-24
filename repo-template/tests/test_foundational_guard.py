"""Tests for the vendored foundational-policy CI guard.

The guard script lives at repo-template/.github/scripts/foundational_guard.py
and is copied verbatim into a diocese policy repo, so it must stay
standalone. We load it by path here rather than importing a package.
"""
import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "foundational_guard.py"
)


def _load_guard():
    import sys
    spec = importlib.util.spec_from_file_location("foundational_guard", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["foundational_guard"] = mod
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
