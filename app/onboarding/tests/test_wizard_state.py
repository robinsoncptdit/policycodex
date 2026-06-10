"""Tests for the session-backed wizard state (APP-08 / DISC-03)."""
from app.onboarding.state import SESSION_KEY, WizardState


class FakeSession(dict):
    """Minimal stand-in for a Django session: a dict that also tracks `modified`."""
    modified = False


def test_initializes_with_first_step_and_flags_modified():
    s = FakeSession()
    state = WizardState(s)
    assert state.current_step == "admin-account"
    assert SESSION_KEY in s
    assert s.modified is True


def test_set_and_get_data_round_trip():
    s = FakeSession()
    state = WizardState(s)
    state.set_data("github-repo", {"repo": "x"})
    assert state.get_data("github-repo") == {"repo": "x"}
    assert state.get_data("configuration") == {}


def test_mark_complete_is_idempotent():
    s = FakeSession()
    state = WizardState(s)
    state.mark_complete("admin-account")
    state.mark_complete("admin-account")
    assert state.is_complete("admin-account") is True
    assert s[SESSION_KEY]["completed"] == ["admin-account"]


def test_furthest_step_tracks_highest_index():
    s = FakeSession()
    state = WizardState(s)
    state.mark_complete("admin-account")   # index 0
    state.mark_complete("llm-provider")    # index 2
    state.set_current("github-app")        # index 1
    assert state.furthest_step() == "llm-provider"


def test_persists_across_fresh_state_over_same_session():
    s = FakeSession()
    WizardState(s).set_data("github-repo", {"years": 7})
    assert WizardState(s).get_data("github-repo") == {"years": 7}


def test_reset_clears_state():
    s = FakeSession()
    state = WizardState(s)
    state.set_data("admin-account", {"a": 1})
    state.reset()
    assert SESSION_KEY not in s
