"""Tests for the read-only policy detail view (APP-23)."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from ingest.policy_reader import LogicalPolicy

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def _stub_policy(
    *, slug, kind="flat", title=None, body="",
    foundational=False, provides=(), frontmatter=None,
):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    pp = (
        Path(f"/tmp/policies/{slug}.md")
        if kind == "flat"
        else Path(f"/tmp/policies/{slug}/policy.md")
    )
    fm = {"title": title or slug.replace("-", " ").title()}
    if frontmatter:
        fm.update(frontmatter)
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter=fm,
        body=body,
        foundational=foundational,
        provides=provides,
    )


def _get_detail(client, slug, policies, open_prs=None):
    """GET /policies/<slug>/ with the working copy + reader + provider stubbed."""
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs or []
                    return client.get(f"/policies/{slug}/")


def test_policy_detail_url_resolves():
    assert reverse("policy_detail", kwargs={"slug": "onboarding"}) == "/policies/onboarding/"


def test_policy_detail_requires_login(client):
    response = client.get("/policies/onboarding/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/onboarding/" in response.url


def test_policy_detail_404_for_unknown_slug(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="something-else", kind="flat")]
    response = _get_detail(client, "no-such-policy", policies)
    assert response.status_code == 404


def test_policy_detail_renders_title(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="New Employee Onboarding")]
    response = _get_detail(client, "onboarding", policies)
    assert response.status_code == 200
    assert "New Employee Onboarding" in response.content.decode()
