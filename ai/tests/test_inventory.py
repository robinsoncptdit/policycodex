"""Unit tests for the AI-10 inventory-pass orchestrator."""
import re

from ai.inventory import (
    InventoryResult,
    REQUIRED_CAPABILITIES,
    _slugify,
    make_inventory_branch_name,
)


def test_required_capabilities():
    assert REQUIRED_CAPABILITIES == ("classifications", "retention-schedule")


def test_slugify_basic():
    assert _slugify("IT Acceptable Use Policy") == "it-acceptable-use-policy"


def test_slugify_strips_punctuation_and_collapses():
    assert _slugify("By-Laws (2021): Final!!") == "by-laws-2021-final"


def test_slugify_empty_falls_back():
    assert _slugify("   ") == "policy"
    assert _slugify("@@@") == "policy"


def test_make_inventory_branch_name_is_not_slug_mapped():
    from app.git_provider.states import branch_to_slug

    name = make_inventory_branch_name()
    assert re.fullmatch(r"policycodex/inventory-[0-9a-f]{8}", name)
    # Deliberately NOT slug-mapped: the catalog gate lookup must ignore this
    # bulk-import branch (mirrors the onboarding init branch).
    assert branch_to_slug(name) is None


def test_inventory_result_defaults_empty():
    result = InventoryResult()
    assert result.written == []
    assert result.skipped_existing == []
    assert result.skipped_empty == []
    assert result.skipped_unsupported == []
    assert result.errors == {}
    assert result.pr is None
