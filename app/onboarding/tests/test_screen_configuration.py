"""DISC-08: Screen 5 configuration — four sections, smart defaults."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    User.objects.create_superuser("admin", "a@b.com", "pw")
    c = Client()
    c.login(username="admin", password="pw")
    # Pre-seed wizard state so gating Signal 3 allows reaching configuration (index 4).
    session = c.session
    session["onboarding"] = {
        "current_step": "configuration",
        "completed": ["admin-account", "github-app", "llm-provider", "github-repo"],
        "data": {},
    }
    session.save()
    return c


def test_get_renders_with_la_defaults(logged_in_admin):
    r = logged_in_admin.get("/onboarding/configuration/")
    assert r.status_code == 200
    assert b"chapter-section-item" in r.content
    assert b"semver" in r.content
    assert b"CFO" in r.content
    assert b"7" in r.content  # default retention years


def test_accept_defaults_advances(logged_in_admin):
    r = logged_in_admin.post("/onboarding/configuration/", {
        "action": "continue",
        "address_scheme": "chapter-section-item",
        "versioning": "semver",
        "reviewer_roles": "CFO,HR Director,General Counsel",
        "retention_admin_years": "7",
        "retention_operational_years": "3",
    })
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/retention-policy/")


def test_custom_values_round_trip(logged_in_admin):
    logged_in_admin.post("/onboarding/configuration/", {
        "action": "continue",
        "address_scheme": "department-code",
        "versioning": "semver",
        "reviewer_roles": "COO,Compliance Officer",
        "retention_admin_years": "10",
        "retention_operational_years": "5",
    })
    # After continue, wizard state advances; the next GET to configuration
    # should still show the user's previously saved values via state.get_data.
    # But the gating now blocks because we already completed it. Verify via
    # the session directly:
    session = logged_in_admin.session
    assert session["onboarding"]["data"]["configuration"]["address_scheme"] == "department-code"
    assert "COO" in session["onboarding"]["data"]["configuration"]["reviewer_roles"]
