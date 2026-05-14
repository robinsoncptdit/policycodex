"""Tests for the branch <-> slug naming convention helpers."""
import pytest

from app.git_provider.states import branch_to_slug, slug_to_branch_prefix


def test_slug_to_branch_prefix_simple():
    assert slug_to_branch_prefix("onboarding") == "policycodex/draft-onboarding"


def test_slug_to_branch_prefix_with_hyphens():
    assert slug_to_branch_prefix("document-retention") == "policycodex/draft-document-retention"


def test_branch_to_slug_simple():
    assert branch_to_slug("policycodex/draft-onboarding") == "onboarding"


def test_branch_to_slug_with_hyphens_in_slug():
    assert branch_to_slug("policycodex/draft-document-retention") == "document-retention"


def test_branch_to_slug_with_trailing_suffix():
    """APP-07 may add a per-edit suffix; the slug recovery must tolerate it."""
    assert branch_to_slug("policycodex/draft-onboarding-2") == "onboarding-2"


def test_branch_to_slug_returns_none_for_non_matching_branch():
    assert branch_to_slug("main") is None
    assert branch_to_slug("policycodex/something-else") is None
    assert branch_to_slug("feature/draft-onboarding") is None
    assert branch_to_slug("") is None


def test_round_trip_for_simple_slug():
    """slug_to_branch_prefix produces a branch that branch_to_slug recovers."""
    for slug in ("onboarding", "code-of-conduct", "document-retention"):
        assert branch_to_slug(slug_to_branch_prefix(slug)) == slug


def test_branch_to_slug_recognizes_edit_prefix_with_hex_uuid():
    """APP-07 opens edit PRs on branches `policycodex/edit-<slug>-<8-hex-chars>`.

    The 8-hex-char UUID suffix must be stripped to recover the underlying slug
    so the catalog can join the PR back to its policy row.
    """
    assert branch_to_slug("policycodex/edit-onboarding-abc12345") == "onboarding"
    assert branch_to_slug("policycodex/edit-code-of-conduct-deadbeef") == "code-of-conduct"


def test_branch_to_slug_edit_prefix_requires_hex_suffix():
    """An `edit-` branch without a trailing 8-hex-char block is not a recognized
    APP-07 edit branch and must return None rather than guess at the slug."""
    assert branch_to_slug("policycodex/edit-onboarding") is None
    assert branch_to_slug("policycodex/edit-onboarding-toolong9") is None
