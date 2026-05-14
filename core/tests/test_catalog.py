"""Tests for the catalog list view."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


@pytest.fixture
def stub_gh_provider():
    """Patch GitHubProvider used by core.views to a MagicMock with list_open_prs=[].

    Tests that need a non-empty open-PR set override this by re-patching the
    same path inside the test body (the inner `with patch(...)` wins).
    """
    with patch("core.views.GitHubProvider") as MockProvider:
        MockProvider.return_value.list_open_prs.return_value = []
        yield MockProvider


def test_catalog_url_resolves():
    assert reverse("catalog") == "/catalog/"


def test_catalog_requires_login(client):
    response = client.get("/catalog/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/catalog/" in response.url


def test_catalog_empty_state_when_repo_url_unset(client, user):
    client.force_login(user)
    with override_settings(POLICYCODEX_POLICY_REPO_URL=""):
        response = client.get("/catalog/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "No policies yet" in body
    # Onboarding hint should appear in the empty state.
    assert "pull_working_copy" in body or "onboarding" in body.lower()


def _stub_policy(*, slug, kind="flat", title=None, foundational=False, provides=()):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from pathlib import Path
    from ingest.policy_reader import LogicalPolicy
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter={"title": title or slug.replace("-", " ").title()},
        body="",
        foundational=foundational,
        provides=provides,
    )


def test_catalog_renders_policies_when_working_copy_exists(client, user, stub_gh_provider):
    """Three policies (2 flat, 1 bundle) render with their titles."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="onboarding", kind="flat", title="New Employee Onboarding"),
        _stub_policy(slug="code-of-conduct", kind="flat", title="Code of Conduct"),
        _stub_policy(
            slug="retention",
            kind="bundle",
            title="Document Retention Policy",
            foundational=True,
            provides=("classifications", "retention-schedule"),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "New Employee Onboarding" in body
    assert "Code of Conduct" in body
    assert "Document Retention Policy" in body


def test_catalog_distinguishes_flat_from_bundle(client, user, stub_gh_provider):
    """Both kind badges appear in the rendered list."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="flat-one", kind="flat"),
        _stub_policy(slug="bundle-one", kind="bundle", foundational=True, provides=("classifications",)),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    assert "flat" in body.lower()
    assert "bundle" in body.lower()


def test_catalog_marks_foundational_bundles(client, user, stub_gh_provider):
    """The `(foundational)` marker appears on foundational policies only."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="plain", kind="flat", foundational=False),
        _stub_policy(
            slug="retention",
            kind="bundle",
            title="Retention Bundle",
            foundational=True,
            provides=("classifications", "retention-schedule"),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/catalog/")

    body = response.content.decode()
    # The bundle policy's section in the body should contain the marker;
    # the flat policy's should not.
    assert "(foundational)" in body
    # Crude check: the marker appears exactly once, attached to "Retention Bundle".
    assert body.count("(foundational)") == 1


def test_catalog_empty_state_when_policies_dir_missing(client, user):
    """When config resolves but policies_dir does not exist, show empty state."""
    client.force_login(user)
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=False):
            response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "No policies yet" in body


def test_root_redirects_authenticated_user_to_catalog(client, user):
    """For an authenticated user, GET / redirects to /catalog/."""
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/catalog/"


def test_root_redirects_unauthenticated_user_to_login(client):
    """For an unauthenticated user, GET / redirects to /catalog/ first, which then
    redirects to /login/. We assert the immediate redirect target is /catalog/
    (the @login_required chain happens at /catalog/, not at /)."""
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    # Follow the chain.
    response = client.get(response.url)
    assert response.status_code == 302
    assert response.url.startswith("/login/")


def test_catalog_shows_published_gate_for_policies_without_open_pr(client, user):
    """Default gate when no open PR exists for the policy's slug."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="onboarding", kind="flat", title="Onboarding"),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = []
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert response.status_code == 200
    # A Published badge appears for the row.
    assert "gate-published" in body
    assert "Published" in body


def test_catalog_shows_drafted_gate_when_open_pr_has_no_approval(client, user):
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat", title="Onboarding")]
    open_prs = [{
        "pr_number": 1,
        "head_branch": "policycodex/draft-onboarding",
        "gate": "drafted",
        "url": "https://example.com/p/1",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert "gate-drafted" in body
    assert "Drafted" in body
    assert "gate-published" not in body


def test_catalog_shows_reviewed_gate_when_open_pr_is_approved(client, user):
    client.force_login(user)
    policies = [_stub_policy(
        slug="retention",
        kind="bundle",
        title="Retention",
        foundational=True,
        provides=("classifications",),
    )]
    open_prs = [{
        "pr_number": 9,
        "head_branch": "policycodex/draft-retention",
        "gate": "reviewed",
        "url": "https://example.com/p/9",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    assert "gate-reviewed" in body
    assert "Reviewed" in body


def test_catalog_mixed_gates_render_correctly(client, user):
    """Three policies: one with no PR, one drafted, one reviewed."""
    client.force_login(user)
    policies = [
        _stub_policy(slug="a-no-pr", kind="flat"),
        _stub_policy(slug="b-drafted", kind="flat"),
        _stub_policy(slug="c-reviewed", kind="flat"),
    ]
    open_prs = [
        {"pr_number": 1, "head_branch": "policycodex/draft-b-drafted", "gate": "drafted", "url": "u1"},
        {"pr_number": 2, "head_branch": "policycodex/draft-c-reviewed", "gate": "reviewed", "url": "u2"},
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    # One of each badge appears.
    assert body.count("gate-published") == 1
    assert body.count("gate-drafted") == 1
    assert body.count("gate-reviewed") == 1


def test_catalog_ignores_open_prs_whose_head_branch_is_not_convention(client, user):
    """A PR on a branch like `feature/something` does not match any slug; it
    should be silently ignored (no crash, no misattribution)."""
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    open_prs = [{
        "pr_number": 99,
        "head_branch": "feature/unrelated",
        "gate": "drafted",
        "url": "u99",
    }]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.return_value = open_prs
                    response = client.get("/catalog/")

    body = response.content.decode()
    # The unrelated PR did not match; the policy still shows Published.
    assert "gate-published" in body
    assert "gate-drafted" not in body


def test_catalog_degrades_gracefully_when_list_open_prs_raises(client, user):
    """Provider raising RuntimeError (e.g., network failure or unconfigured
    credentials) must not 500 the catalog. The page renders with every policy
    treated as Published."""
    client.force_login(user)
    policies = [_stub_policy(slug="onboarding", kind="flat")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.list_open_prs.side_effect = RuntimeError("network down")
                    response = client.get("/catalog/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "gate-published" in body
