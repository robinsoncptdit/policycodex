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
    spec = importlib.util.spec_from_file_location("foundational_guard", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
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
