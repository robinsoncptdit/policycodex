"""Tests for the policy_edit view (APP-07)."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse

from ingest.policy_reader import LogicalPolicy

User = get_user_model()


@pytest.fixture
def user(db):
    user = User.objects.create_user(
        username="editor",
        password="hunter2hunter2",
        email="editor@example.com",
        first_name="Pat",
        last_name="Editor",
    )
    user.profile.must_change_password = False
    user.profile.save()
    user.groups.add(Group.objects.get(name="Editor"))
    return user


def _stub_policy(*, slug, kind="flat", title=None, body="", foundational=False, provides=()):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy.

    Mirrors core/tests/test_catalog.py:_stub_policy so behavior stays consistent.
    """
    pp = Path(f"/tmp/policies/{slug}.md") if kind == "flat" else Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind=kind,
        policy_path=pp,
        data_path=None if kind == "flat" else pp.parent / "data.yaml",
        frontmatter={"title": title or slug.replace("-", " ").title()},
        body=body,
        foundational=foundational,
        provides=provides,
    )


# --- URL + auth ---

def test_policy_edit_url_resolves():
    assert reverse("policy_edit", kwargs={"slug": "onboarding"}) == "/policies/onboarding/edit/"


def test_policy_edit_requires_login(client):
    response = client.get("/policies/onboarding/edit/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/onboarding/edit/" in response.url


def test_policy_edit_404_when_slug_not_found(client, user):
    """An authenticated request for a non-existent slug returns 404."""
    client.force_login(user)
    policies = [_stub_policy(slug="exists")]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/policies/missing/edit/")
    assert response.status_code == 404


# --- Form class ---

def test_form_has_three_fields():
    """v0.1 editable surface: title, body, summary."""
    from core.forms import PolicyEditForm
    form = PolicyEditForm()
    assert set(form.fields.keys()) == {"title", "body", "summary"}


def test_form_required_fields():
    from core.forms import PolicyEditForm
    form = PolicyEditForm(data={"title": "", "body": "", "summary": ""})
    assert not form.is_valid()
    assert "title" in form.errors
    assert "body" in form.errors
    # summary is optional.
    assert "summary" not in form.errors


def test_form_title_max_length():
    """Title is capped at 200 chars to keep PR titles bounded."""
    from core.forms import PolicyEditForm
    long_title = "x" * 201
    form = PolicyEditForm(data={"title": long_title, "body": "ok"})
    assert not form.is_valid()
    assert "title" in form.errors


# --- GET pre-population ---

def test_get_renders_form_prepopulated_with_title_and_body(client, user):
    """A GET on /policies/<slug>/edit/ pre-populates title from frontmatter and body verbatim."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="onboarding",
            kind="flat",
            title="New Employee Onboarding",
            body="## Purpose\nWelcome new hires.\n",
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.get("/policies/onboarding/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    # Title field pre-populated.
    assert 'value="New Employee Onboarding"' in body
    # Body textarea pre-populated. Django escapes content, so check the unescaped string.
    assert "## Purpose" in body
    assert "Welcome new hires." in body
    # Form structure visible.
    assert "<form" in body
    assert 'method="post"' in body
    assert "csrfmiddlewaretoken" in body


# --- Foundational-policy gate ---

def test_get_foundational_policy_returns_403_with_explanation(client, user):
    """Foundational bundles edit through the typed-table UI (APP-20), not this form.

    GET on a foundational policy returns 403 with a custom template that
    names the typed-table UI as the right path. Per the foundational-policy
    design (L1 protection layer)."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="document-retention",
            kind="bundle",
            title="Document Retention Policy",
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
                response = client.get("/policies/document-retention/edit/")
    assert response.status_code == 403
    body = response.content.decode()
    assert "foundational" in body.lower()
    # The error page must mention the slug so the user knows what was rejected.
    assert "document-retention" in body
    # And link back to the catalog.
    assert "/catalog/" in body


def test_post_foundational_policy_also_returns_403(client, user):
    """The gate applies to POST as well, never let a foundational policy be edited via this form."""
    client.force_login(user)
    policies = [
        _stub_policy(
            slug="document-retention",
            kind="bundle",
            foundational=True,
            provides=("classifications",),
        ),
    ]
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                response = client.post(
                    "/policies/document-retention/edit/",
                    data={"title": "Hijack", "body": "Bad", "summary": ""},
                )
    assert response.status_code == 403


# --- POST happy path ---

def test_post_valid_invokes_propose_change_with_expected_args(client, user, tmp_path):
    """The happy path writes the file then funnels through propose_change with
    the right kwargs. Call-order of branch/commit/push/open_pr lives in
    app/git_provider/tests/test_propose.py; here we only check the view's contract."""
    client.force_login(user)

    # Build a real on-disk policies/onboarding.md so the view can write to it.
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text(
        "---\ntitle: Old Title\nowner: HR Director\n---\nOld body.\n",
        encoding="utf-8",
    )

    # Real LogicalPolicy so the view can read it back from the reader mock.
    real_policy = LogicalPolicy(
        slug="onboarding",
        kind="flat",
        policy_path=policy_file,
        data_path=None,
        frontmatter={"title": "Old Title", "owner": "HR Director"},
        body="Old body.\n",
        foundational=False,
        provides=(),
    )

    fake_pr = {
        "pr_number": 17,
        "url": "https://github.com/example/diocese-policies/pull/17",
        "state": "open",
    }
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change", return_value=fake_pr) as mock_propose:
                        response = client.post(
                            "/policies/onboarding/edit/",
                            data={
                                "title": "Onboarding Revised",
                                "body": "New body text.\n",
                                "summary": "Tighten the welcome section",
                            },
                        )

    # Successful POST renders the success page.
    assert response.status_code in (302, 200)
    # File on disk reflects the new title + body (round-tripped through _render_policy_md).
    new_text = policy_file.read_text(encoding="utf-8")
    assert "title: Onboarding Revised" in new_text
    assert "owner: HR Director" in new_text  # unexposed key preserved
    assert "New body text." in new_text
    # propose_change called once with expected kwargs.
    mock_propose.assert_called_once()
    kwargs = mock_propose.call_args.kwargs
    assert kwargs["default_branch"] == "main"
    assert kwargs["branch_name"].startswith("policycodex/edit-onboarding-")
    assert kwargs["files"] == [policy_file]
    assert kwargs["commit_message"] == "Tighten the welcome section"
    assert kwargs["author_name"] == "Pat Editor"
    assert kwargs["author_email"] == "editor@example.com"
    assert "onboarding" in kwargs["pr_title"]
    assert "Tighten the welcome section" in kwargs["pr_title"]
    assert "Opened by PolicyCodex on behalf of editor" in kwargs["pr_body"]


def test_post_default_commit_message_when_summary_empty(client, user, tmp_path):
    """If the form's summary is blank, the commit message defaults to `Update <slug>`."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nbody\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="body\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider"):
                    with patch(
                        "core.views.propose_change",
                        return_value={"pr_number": 1, "url": "u", "state": "open"},
                    ) as mock_propose:
                        client.post(
                            "/policies/onboarding/edit/",
                            data={"title": "T2", "body": "b2\n", "summary": ""},
                        )
    assert mock_propose.call_args.kwargs["commit_message"] == "Update onboarding"


def test_post_renders_success_page_with_pr_url(client, user, tmp_path):
    """After a successful PR is opened, the user sees a success page containing the PR URL."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    fake_pr = {
        "pr_number": 42,
        "url": "https://github.com/example/diocese-policies/pull/42",
        "state": "open",
    }
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change", return_value=fake_pr):
                        response = client.post(
                            "/policies/onboarding/edit/",
                            data={"title": "T2", "body": "b2\n", "summary": "msg"},
                            follow=True,
                        )
    assert response.status_code == 200
    body = response.content.decode()
    assert "https://github.com/example/diocese-policies/pull/42" in body
    assert "42" in body  # PR number visible somewhere


# --- Provider failure paths ---

@pytest.mark.parametrize("raised_exc", [
    RuntimeError("git push failed"),
    ValueError("bad value"),
    Exception("unexpected"),
])
def test_post_renders_form_with_error_on_propose_change_failure(
    client, user, tmp_path, raised_exc,
):
    """When propose_change raises anything (network error, git failure, ...),
    the form re-renders with a user-visible error and HTTP 200 (not 500).
    propose_change itself restores a clean default branch on failure
    (covered by app/git_provider/tests/test_propose.py)."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change", side_effect=raised_exc):
                        response = client.post(
                            "/policies/onboarding/edit/",
                            data={"title": "T2", "body": "b2\n", "summary": "msg"},
                        )
    # No 500.
    assert response.status_code == 200
    body = response.content.decode()
    # The edit form is re-rendered (not the success page).
    assert "Open PR" in body  # the submit button label
    # User input is preserved.
    assert 'value="T2"' in body
    assert "b2" in body
    # A user-facing error message is present.
    assert "couldn't" in body.lower() or "failed" in body.lower() or "error" in body.lower()


def test_post_invalid_form_rerenders_with_errors(client, user, tmp_path):
    """Missing required fields re-renders the form with field errors and HTTP 200."""
    client.force_login(user)
    repo_dir = tmp_path / "diocese-policies"
    policies_dir = repo_dir / "policies"
    policies_dir.mkdir(parents=True)
    policy_file = policies_dir / "onboarding.md"
    policy_file.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    real_policy = LogicalPolicy(
        slug="onboarding", kind="flat", policy_path=policy_file, data_path=None,
        frontmatter={"title": "T"}, body="b\n", foundational=False, provides=(),
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change") as mock_propose:
                        response = client.post(
                            "/policies/onboarding/edit/",
                            data={"title": "", "body": "", "summary": ""},
                        )
                        # propose_change NEVER called because form was invalid.
                        mock_propose.assert_not_called()
    assert response.status_code == 200
    body = response.content.decode()
    # Form re-rendered with errors (Django's default error label or the field error UL).
    assert "required" in body.lower() or "errorlist" in body.lower() or "This field" in body
