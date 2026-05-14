"""Tests for the per-policy .policymeta.yaml sidecar reader."""
from pathlib import Path

import pytest


def test_read_pr_number_for_flat_policy(tmp_path):
    """A flat policy stores its sidecar at policies/<slug>.policymeta.yaml."""
    from core.policymeta import read_pr_number_for
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "code-of-conduct.md").write_text("---\ntitle: x\n---\n")
    (policies / "code-of-conduct.policymeta.yaml").write_text("pr_number: 42\n")
    assert read_pr_number_for(tmp_path, "code-of-conduct") == 42


def test_read_pr_number_for_bundle_policy(tmp_path):
    """A bundle policy stores its sidecar at policies/<slug>/.policymeta.yaml."""
    from core.policymeta import read_pr_number_for
    bundle = tmp_path / "policies" / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text("---\nfoundational: true\n---\n")
    (bundle / ".policymeta.yaml").write_text("pr_number: 99\n")
    assert read_pr_number_for(tmp_path, "document-retention") == 99


def test_read_pr_number_returns_none_when_sidecar_absent(tmp_path):
    """No sidecar means the policy has never been edited via the app; return None."""
    from core.policymeta import read_pr_number_for
    (tmp_path / "policies").mkdir()
    assert read_pr_number_for(tmp_path, "never-edited") is None


def test_read_pr_number_returns_none_when_policies_dir_absent(tmp_path):
    """No policies dir means a fresh install; return None (not an error)."""
    from core.policymeta import read_pr_number_for
    assert read_pr_number_for(tmp_path, "anything") is None


def test_read_pr_number_raises_on_malformed_yaml(tmp_path):
    """A corrupted sidecar should surface clearly rather than silently returning None."""
    from core.policymeta import read_pr_number_for, PolicymetaError
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "broken.policymeta.yaml").write_text("not: [valid: yaml")
    with pytest.raises(PolicymetaError, match="policymeta"):
        read_pr_number_for(tmp_path, "broken")


def test_read_pr_number_raises_when_pr_number_missing(tmp_path):
    """A sidecar with no pr_number key is malformed."""
    from core.policymeta import read_pr_number_for, PolicymetaError
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "no-pr.policymeta.yaml").write_text("other_field: x\n")
    with pytest.raises(PolicymetaError, match="pr_number"):
        read_pr_number_for(tmp_path, "no-pr")
