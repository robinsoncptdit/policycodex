"""Tests for the onboarding step registry (APP-08 / DISC-03)."""
from app.onboarding.wizard import (
    STEPS,
    first_step,
    get_step,
    index_of,
    is_last,
    next_step,
    prev_step,
)


def test_steps_tuple_has_seven_slugs_in_disc_order():
    slugs = [s.slug for s in STEPS]
    assert slugs == [
        "admin-account",
        "github-app",
        "llm-provider",
        "github-repo",
        "configuration",
        "retention-policy",
        "policy-documents",
    ]


def test_first_step():
    assert first_step().slug == "admin-account"


def test_get_step_known_and_unknown():
    assert get_step("github-repo").title == "Policy repository"
    assert get_step("nope") is None


def test_index_of():
    assert index_of("admin-account") == 0
    assert index_of("policy-documents") == 6
    assert index_of("nope") is None


def test_next_step():
    assert next_step("admin-account").slug == "github-app"
    assert next_step("policy-documents") is None
    assert next_step("nope") is None


def test_prev_step():
    assert prev_step("github-app").slug == "admin-account"
    assert prev_step("admin-account") is None
    assert prev_step("nope") is None


def test_is_last():
    assert is_last("policy-documents") is True
    assert is_last("admin-account") is False
