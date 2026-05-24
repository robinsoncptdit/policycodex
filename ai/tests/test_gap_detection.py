"""Tests for ai.gap_detection (AI-13: retention gap detection)."""
from ai.gap_detection import find_gaps, is_gap, known_types


def test_known_types_collects_ids_and_names():
    # Distinct id and name tokens so this independently proves BOTH are harvested.
    classifications = [
        {"id": "fin", "name": "Financial"},
        {"id": "hr", "name": "Personnel"},
    ]
    assert known_types(classifications) == {
        "fin", "financial", "hr", "personnel",
    }


def test_known_types_casefolds_and_strips():
    assert known_types([{"id": " Financial ", "name": "FINANCE"}]) == {
        "financial", "finance",
    }


def test_known_types_skips_non_dict_and_missing_keys():
    classifications = [
        {"id": "ok"},
        "not-a-dict",
        {"name": None},
        {},
    ]
    assert known_types(classifications) == {"ok"}


def test_known_types_empty_or_none():
    assert known_types([]) == set()
    assert known_types(None) == set()


def test_is_gap_known_category_is_false():
    known = {"financial"}
    assert is_gap("Financial", known) is False


def test_is_gap_unknown_category_is_true():
    assert is_gap("Marketing", {"financial"}) is True


def test_is_gap_missing_category_is_true():
    assert is_gap(None, {"financial"}) is True
    assert is_gap("", {"financial"}) is True
    assert is_gap("   ", {"financial"}) is True


def test_is_gap_is_case_insensitive():
    assert is_gap("  finANCIAL ", {"financial"}) is False


def test_find_gaps_returns_only_gaps_in_order():
    classifications = [{"id": "financial"}, {"name": "Personnel"}]
    items = [
        ("a", "Financial"),     # known
        ("b", "Marketing"),     # gap
        ("c", None),            # gap (missing)
        ("d", "personnel"),     # known (name, casefold)
    ]
    assert find_gaps(items, classifications) == ["b", "c"]


def test_find_gaps_deprecated_classification_counts_as_known():
    # A deprecated classification stays in the list, so a policy using it is
    # not a gap (deprecated ids remain valid for existing references).
    classifications = [{"id": "legacy", "name": "Legacy", "deprecated": True}]
    assert find_gaps([("x", "Legacy")], classifications) == []
