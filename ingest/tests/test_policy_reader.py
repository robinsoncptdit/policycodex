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


def _make_bundle(
    policies_root: Path,
    slug: str,
    *,
    provides: list[str] | None = None,
    extra_frontmatter: dict | None = None,
    data_payload: dict | None = None,
) -> Path:
    """Create policies/<slug>/{policy.md, data.yaml} for a foundational bundle."""
    bundle = policies_root / slug
    bundle.mkdir()
    fm = {
        "title": slug.replace("-", " ").title(),
        "owner": "CFO",
        "foundational": True,
        "provides": provides or ["classifications"],
    }
    if extra_frontmatter:
        fm.update(extra_frontmatter)
    import yaml as _yaml
    fm_text = _yaml.safe_dump(fm, sort_keys=False).strip()
    (bundle / "policy.md").write_text(
        f"---\n{fm_text}\n---\n# {slug}\n", encoding="utf-8"
    )
    data = data_payload if data_payload is not None else {"classifications": [{"id": "x", "name": "X"}]}
    (bundle / "data.yaml").write_text(_yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return bundle


def test_bundle_yields_single_logical_policy(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "retention", provides=["classifications", "retention-schedule"])

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    assert len(results) == 1
    p = results[0]
    assert p.slug == "retention"
    assert p.kind == "bundle"
    assert p.policy_path == policies / "retention" / "policy.md"
    assert p.data_path == policies / "retention" / "data.yaml"
    assert p.foundational is True
    assert p.provides == ("classifications", "retention-schedule")
