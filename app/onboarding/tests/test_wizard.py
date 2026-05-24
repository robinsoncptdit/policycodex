"""Tests for the onboarding step registry (APP-08)."""
from app.onboarding.wizard import (
    STEPS,
    first_step,
    get_step,
    index_of,
    is_last,
    next_step,
    prev_step,
)


def test_registry_has_seven_steps_in_order():
    assert [s.slug for s in STEPS] == [
        "github-repo",
        "address-scheme",
        "versioning",
        "reviewer-roles",
        "retention",
        "llm-provider",
        "retention-policy",
    ]


def test_first_step():
    assert first_step().slug == "github-repo"


def test_get_step_known_and_unknown():
    assert get_step("versioning").title == "Versioning convention"
    assert get_step("nope") is None


def test_index_of():
    assert index_of("github-repo") == 0
    assert index_of("retention-policy") == 6
    assert index_of("nope") is None


def test_next_step():
    assert next_step("github-repo").slug == "address-scheme"
    assert next_step("retention-policy") is None
    assert next_step("nope") is None


def test_prev_step():
    assert prev_step("address-scheme").slug == "github-repo"
    assert prev_step("github-repo") is None
    assert prev_step("nope") is None


def test_is_last():
    assert is_last("retention-policy") is True
    assert is_last("github-repo") is False
