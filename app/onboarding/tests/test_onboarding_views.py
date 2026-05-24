"""Tests for the onboarding wizard views (APP-08)."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


# A valid github-repo form payload, for tests that POST `continue` past step 1.
GITHUB_REPO_CONTINUE = {
    "action": "continue",
    "mode": "connect",
    "repo_url": "https://github.com/acme/policies",
    "branch": "main",
}


def test_urls_resolve():
    assert reverse("onboarding") == "/onboarding/"
    assert reverse("onboarding_step", kwargs={"step": "github-repo"}) == "/onboarding/github-repo/"


def test_onboarding_requires_login(client):
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
    # The per-step view is guarded too.
    step_resp = client.get("/onboarding/github-repo/")
    assert step_resp.status_code == 302
    assert step_resp.url.startswith("/login/")


def test_root_redirects_to_first_step_when_fresh(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_get_step_renders_title_and_indicator(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "GitHub repository" in body
    assert "Step 1 of 7" in body


def test_unknown_step_returns_404(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/not-a-step/")
    assert resp.status_code == 404


def test_ahead_jump_is_gated(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/versioning/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_continue_advances_and_marks_complete(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    assert client.get("/onboarding/").url == "/onboarding/address-scheme/"


def test_back_goes_to_previous_step(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    resp = client.post("/onboarding/address-scheme/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_back_on_first_step_is_noop_redirect(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_save_exit_redirects_to_catalog(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "save_exit"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_can_revisit_completed_step_without_trapping(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert client.get("/onboarding/github-repo/").status_code == 200
    assert client.get("/onboarding/address-scheme/").status_code == 200


def test_last_step_continue_completes_and_redirects_to_catalog(client, user):
    client.force_login(user)
    slugs = [
        "github-repo", "address-scheme", "versioning", "reviewer-roles",
        "retention", "llm-provider", "retention-policy",
    ]
    for slug in slugs[:-1]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})
    resp = client.post("/onboarding/retention-policy/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_github_repo_get_renders_form(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Mode radio + the connect URL field render.
    assert 'name="mode"' in body
    assert 'name="repo_url"' in body


def test_github_repo_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    # Missing repo_url for connect mode -> invalid.
    resp = client.post("/onboarding/github-repo/", {"action": "continue", "mode": "connect", "branch": "main"})
    assert resp.status_code == 200  # re-rendered, not redirected
    # Still on github-repo (not advanced); the step is not marked complete.
    assert client.get("/onboarding/").url == "/onboarding/github-repo/"


def test_github_repo_valid_continue_persists_and_advances(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    # The captured value is persisted and pre-populates a return visit.
    back = client.get("/onboarding/github-repo/")
    assert "https://github.com/acme/policies" in back.content.decode()


def test_no_form_step_still_advances_on_bare_continue(client, user):
    """Regression: a step with no registered form keeps the no-op continue."""
    client.force_login(user)
    # Advance past the form step first.
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    # address-scheme has no form; a bare continue advances.
    resp = client.post("/onboarding/address-scheme/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/versioning/"
