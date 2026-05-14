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


def test_mixed_structure_yields_alpha_sorted_entries(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    # Intentionally not in alpha order:
    _make_flat(policies, "onboarding")
    _make_bundle(policies, "retention", provides=["classifications"])
    _make_flat(policies, "code-of-conduct")
    _make_bundle(policies, "appendix-a", provides=["retention-schedule"])

    reader = BundleAwarePolicyReader(policies)
    results = list(reader.read())

    slugs = [p.slug for p in results]
    assert slugs == ["appendix-a", "code-of-conduct", "onboarding", "retention"]
    kinds = {p.slug: p.kind for p in results}
    assert kinds == {
        "appendix-a": "bundle",
        "code-of-conduct": "flat",
        "onboarding": "flat",
        "retention": "bundle",
    }


def test_hidden_entries_skipped(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "real")
    (policies / ".hidden.md").write_text("---\n---\nx", encoding="utf-8")
    hidden_dir = policies / ".dotdir"
    hidden_dir.mkdir()
    (hidden_dir / "policy.md").write_text(
        "---\nfoundational: true\nprovides: [x]\n---\n", encoding="utf-8"
    )

    reader = BundleAwarePolicyReader(policies)
    assert [p.slug for p in reader.read()] == ["real"]


def test_non_md_top_level_files_skipped(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_flat(policies, "real")
    (policies / "README.txt").write_text("ignore me", encoding="utf-8")
    (policies / "schema.json").write_text("{}", encoding="utf-8")

    reader = BundleAwarePolicyReader(policies)
    assert [p.slug for p in reader.read()] == ["real"]


def test_bundle_missing_policy_md_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="missing policy.md"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_missing_data_yaml_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: [classifications]\n---\n", encoding="utf-8"
    )

    with pytest.raises(BundleError, match="missing data.yaml"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_without_foundational_flag_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    _make_bundle(policies, "retention", extra_frontmatter={"foundational": False})

    with pytest.raises(BundleError, match="foundational"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_without_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_empty_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: []\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_non_list_provides_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: classifications\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(BundleError, match="provides"):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_invalid_yaml_frontmatter_raises(tmp_path):
    import yaml as _yaml
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides:\n  - [unbalanced\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications: []\n", encoding="utf-8")

    with pytest.raises(_yaml.YAMLError):
        list(BundleAwarePolicyReader(policies).read())


def test_bundle_with_invalid_yaml_data_raises(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    bundle = policies / "retention"
    bundle.mkdir()
    (bundle / "policy.md").write_text(
        "---\nfoundational: true\nprovides: [classifications]\n---\n", encoding="utf-8"
    )
    (bundle / "data.yaml").write_text("classifications:\n  - [unbalanced\n", encoding="utf-8")

    with pytest.raises(BundleError, match="data.yaml"):
        list(BundleAwarePolicyReader(policies).read())


def test_missing_policies_root_raises(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError, match="policies root"):
        list(BundleAwarePolicyReader(missing).read())


def test_policies_root_is_not_a_directory_raises(tmp_path):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        list(BundleAwarePolicyReader(not_a_dir).read())


def test_empty_policies_root_yields_no_entries(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    assert list(BundleAwarePolicyReader(policies).read()) == []
