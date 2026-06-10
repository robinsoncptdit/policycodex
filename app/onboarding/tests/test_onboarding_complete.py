"""Tests for the onboarding completion screen (APP-29).

A presentation-only GET view. It derives org/repo from the screen-1
`github-repo` wizard data and reads a best-effort PR url the accept handlers
stash in the session. No network, no git, no AI.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


def _seed_connect(client):
    """Populate screen-1 wizard data via the real form post (connect mode)."""
    client.post(
        "/onboarding/github-repo/",
        {
            "action": "continue",
            "mode": "connect",
            "repo_url": "https://github.com/acme/policies",
            "branch": "main",
        },
    )


def _seed_create(client):
    client.post(
        "/onboarding/github-repo/",
        {
            "action": "continue",
            "mode": "create",
            "org": "acme",
            "repo_name": "policies",
            "branch": "main",
        },
    )


def test_connect_mode_renders_derived_links(client, user, settings):
    settings.POLICYCODEX_SOURCE_URL = "https://github.com/robinsoncptdit/policycodex"
    client.force_login(user)
    _seed_connect(client)
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "https://github.com/acme/policies/settings/pages" in body
    assert "acme.github.io" in body
    assert 'data-copy="acme.github.io"' in body
    assert (
        "https://github.com/robinsoncptdit/policycodex/blob/main/"
        "HOWTO-GitHub-Team-Setup.md" in body
    )
    assert reverse("catalog") in body  # the continue button target


def test_create_mode_renders_derived_links(client, user):
    client.force_login(user)
    _seed_create(client)
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "https://github.com/acme/policies/settings/pages" in body
    assert "acme.github.io" in body


def test_pr_url_present_renders_pr_link(client, user):
    client.force_login(user)
    _seed_connect(client)
    session = client.session
    session["onboarding_pr_url"] = "https://github.com/acme/policies/pull/1"
    session.save()
    resp = client.get(reverse("onboarding-complete"))
    body = resp.content.decode()
    assert "https://github.com/acme/policies/pull/1" in body


def test_pr_url_absent_renders_no_broken_anchor(client, user):
    client.force_login(user)
    _seed_connect(client)
    resp = client.get(reverse("onboarding-complete"))
    body = resp.content.decode()
    assert "/pull/" not in body  # no PR anchor when none was stashed


def test_guard_redirects_when_no_repo_data(client, user):
    client.force_login(user)
    # No github-repo wizard data seeded.
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 302
    assert resp.url == reverse("onboarding")


def test_unauthenticated_redirects_to_login(client, db):
    resp = client.get(reverse("onboarding-complete"))
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
