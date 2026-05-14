"""Tests for the APP-19 publish action view."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="publisher", password="secret")


@pytest.fixture
def working_copy(tmp_path):
    """A minimal working copy with one policy file."""
    repo = tmp_path / "repo"
    policies = repo / "policies"
    policies.mkdir(parents=True)
    (policies / "code-of-conduct.md").write_text("---\ntitle: Code of Conduct\n---\n")
    return repo


def test_publish_policy_url_resolves():
    assert reverse("publish_policy", args=["my-slug"]) == "/policies/my-slug/publish/"


def test_publish_policy_requires_login(client):
    response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


def test_publish_policy_rejects_get(client, user):
    """GET is method-not-allowed; the action is mutation-only."""
    client.force_login(user)
    response = client.get("/policies/code-of-conduct/publish/")
    assert response.status_code == 405


def _patch_view_dependencies(
    *,
    working_dir,
    slug,
    gate_state,
    pr_number=42,
    merge_result=None,
    merge_exception=None,
    open_prs=None,
):
    """Patch the view-layer collaborators. Returns the entered context managers
    so the test can inspect call args.

    `open_prs` may override the default (one PR whose head_branch matches
    `policycodex/edit-<slug>-abcd1234`). Pass `[]` for a "no open PR" case.
    """
    config_mock = MagicMock()
    config_mock.working_dir = working_dir
    fake_provider = MagicMock()
    if open_prs is None:
        open_prs = [
            {
                "pr_number": pr_number,
                "head_branch": f"policycodex/edit-{slug}-abcd1234",
                "gate": gate_state,
                "url": f"https://github.com/x/y/pull/{pr_number}",
            }
        ]
    fake_provider.list_open_prs.return_value = open_prs
    fake_provider.read_pr_state.return_value = gate_state
    if merge_exception is not None:
        fake_provider.merge_pr.side_effect = merge_exception
    elif merge_result is not None:
        fake_provider.merge_pr.return_value = merge_result
    else:
        fake_provider.merge_pr.return_value = {"merged": True, "sha": "abcdef0", "merge_method": "squash"}

    return (
        patch("core.views.load_working_copy_config", return_value=config_mock),
        patch("core.views.GitHubProvider", return_value=fake_provider),
        fake_provider,
    )


def test_publish_policy_happy_path_merges_and_redirects(client, user, working_copy):
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, slug="code-of-conduct", gate_state="reviewed",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.list_open_prs.assert_called_once_with(working_copy)
    fake_provider.read_pr_state.assert_called_once_with(42, working_copy)
    fake_provider.merge_pr.assert_called_once_with(42, working_copy, merge_method="squash")
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("published" in m.lower() or "merged" in m.lower() for m in msgs)


def test_publish_policy_refuses_drafted_pr(client, user, working_copy):
    """Gate guard: a Drafted (not-yet-approved) PR cannot be published."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, slug="code-of-conduct", gate_state="drafted",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("approval" in m.lower() or "reviewed" in m.lower() or "drafted" in m.lower() for m in msgs)


def test_publish_policy_refuses_already_published_pr(client, user, working_copy):
    """An already-merged PR cannot be re-published."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, slug="code-of-conduct", gate_state="published",
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("already" in m.lower() or "published" in m.lower() for m in msgs)


def test_publish_policy_handles_merge_conflict(client, user, working_copy):
    """merge_pr raising RuntimeError surfaces as a clear flash, not a 500."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy,
        slug="code-of-conduct",
        gate_state="reviewed",
        merge_exception=RuntimeError("merge_pr failed for PR #42: 409 Merge conflict"),
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("merge" in m.lower() and ("conflict" in m.lower() or "fail" in m.lower()) for m in msgs)


def test_publish_policy_no_open_pr_for_slug_flashes_error(client, user, working_copy):
    """If no open PR matches the requested slug, flash a clear error rather than 500."""
    client.force_login(user)
    cm_cfg, cm_prov, fake_provider = _patch_view_dependencies(
        working_dir=working_copy, slug="code-of-conduct", gate_state="reviewed",
        open_prs=[],  # no PRs at all
    )
    with cm_cfg, cm_prov:
        response = client.post("/policies/orphan/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("no pending" in m.lower() or "no pull request" in m.lower() or "no pr" in m.lower() for m in msgs)


def test_publish_policy_handles_no_working_copy_configured(client, user):
    """If load_working_copy_config raises, flash error and redirect; do not 500."""
    client.force_login(user)
    with patch("core.views.load_working_copy_config", side_effect=RuntimeError("URL unset")):
        response = client.post("/policies/anything/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("not configured" in m.lower() or "onboarding" in m.lower() for m in msgs)


def test_publish_policy_handles_list_open_prs_failure(client, user, working_copy):
    """If list_open_prs raises (network down / auth expired), flash and redirect."""
    client.force_login(user)
    config_mock = MagicMock()
    config_mock.working_dir = working_copy
    fake_provider = MagicMock()
    fake_provider.list_open_prs.side_effect = RuntimeError("github unreachable")
    with patch("core.views.load_working_copy_config", return_value=config_mock):
        with patch("core.views.GitHubProvider", return_value=fake_provider):
            response = client.post("/policies/code-of-conduct/publish/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.merge_pr.assert_not_called()
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("could not list" in m.lower() or "pull requests" in m.lower() for m in msgs)
