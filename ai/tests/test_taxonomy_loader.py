"""Tests for ai.taxonomy_loader (AI-12-revised: read taxonomy from the bundle)."""
from pathlib import Path

import yaml

from ai.taxonomy_loader import (
    find_foundational_bundle,
    load_foundational_taxonomy,
    resolve_taxonomy,
)

REQUIRED = ("classifications", "retention-schedule")


def _make_bundle(policies_dir, slug, provides, data):
    bundle = policies_dir / slug
    bundle.mkdir(parents=True)
    fm_provides = "\n".join(f"  - {p}" for p in provides)
    (bundle / "policy.md").write_text(
        f"---\nfoundational: true\nprovides:\n{fm_provides}\n---\nBody.\n",
        encoding="utf-8",
    )
    (bundle / "data.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return bundle


def _make_flat(policies_dir, slug):
    (policies_dir / f"{slug}.md").write_text(
        "---\ntitle: Flat\n---\nBody.\n", encoding="utf-8"
    )


def test_find_returns_none_when_dir_missing(tmp_path):
    assert find_foundational_bundle(tmp_path / "nope", REQUIRED) is None


def test_find_returns_none_when_no_matching_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "code-of-conduct")
    assert find_foundational_bundle(policies, REQUIRED) is None


def test_find_returns_data_path_for_matching_bundle(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "code-of-conduct")
    bundle = _make_bundle(
        policies, "document-retention",
        ["classifications", "retention-schedule"],
        {"classifications": [{"id": "a", "name": "A"}], "retention_schedule": []},
    )
    assert find_foundational_bundle(policies, REQUIRED) == bundle / "data.yaml"


def test_find_requires_all_capabilities(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "partial", ["classifications"], {"classifications": []})
    assert find_foundational_bundle(policies, REQUIRED) is None
