"""Tests for BundleAwarePolicyReader."""
from pathlib import Path

import pytest

from ingest.policy_reader import (
    BundleAwarePolicyReader,
    BundleError,
    LogicalPolicy,
)


def _make_flat(policies_root: Path, slug: str, body: str = "# Body\n") -> Path:
    """Create a flat policies/<slug>.md file with minimal frontmatter."""
    p = policies_root / f"{slug}.md"
    p.write_text(
        f"---\ntitle: {slug.title()}\nowner: HR\n---\n{body}",
        encoding="utf-8",
    )
    return p


def test_flat_policy_yields_single_logical_policy(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "onboarding")

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    assert len(results) == 1
    p = results[0]
    assert isinstance(p, LogicalPolicy)
    assert p.slug == "onboarding"
    assert p.kind == "flat"
    assert p.policy_path == policies / "onboarding.md"
    assert p.data_path is None
    assert p.frontmatter["title"] == "Onboarding"
    assert p.foundational is False
    assert p.provides == ()
