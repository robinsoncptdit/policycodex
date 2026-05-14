"""Tests for the policy_edit view (APP-07)."""
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
    return User.objects.create_user(
        username="editor",
        password="hunter2hunter2",
        email="editor@example.com",
        first_name="Pat",
        last_name="Editor",
    )


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

def test_post_valid_calls_branch_commit_push_open_pr_in_order(client, user, tmp_path):
    """The happy path sequences all four GitHubProvider operations and writes the file."""
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
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = fake_pr
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={
                            "title": "Onboarding Revised",
                            "body": "New body text.\n",
                            "summary": "Tighten the welcome section",
                        },
                    )

    # Successful POST redirects to the success page.
    assert response.status_code in (302, 200)  # 302 if redirect-to-success; 200 if render-success-directly
    # File on disk reflects the new title + body (round-tripped through _render_policy_md).
    new_text = policy_file.read_text(encoding="utf-8")
    assert "title: Onboarding Revised" in new_text
    assert "owner: HR Director" in new_text  # unexposed key preserved
    assert "New body text." in new_text
    # GitHubProvider call sequence.
    instance.branch.assert_called_once()
    branch_args = instance.branch.call_args[0]
    branch_name = branch_args[0]
    assert branch_name.startswith("policycodex/edit-onboarding-")
    instance.commit.assert_called_once()
    commit_kwargs = instance.commit.call_args.kwargs or {}
    commit_args = instance.commit.call_args.args
    # commit(message, files, author_name, author_email, working_dir)
    # The view may use kwargs or positional; assert by name when possible.
    # Pull either way:
    def _pick(name, idx):
        if name in commit_kwargs:
            return commit_kwargs[name]
        return commit_args[idx]
    msg = _pick("message", 0)
    files = _pick("files", 1)
    author_name = _pick("author_name", 2)
    author_email = _pick("author_email", 3)
    assert msg == "Tighten the welcome section"
    assert files == [policy_file]
    assert author_name == "Pat Editor"
    assert author_email == "editor@example.com"
    instance.push.assert_called_once()
    push_args = instance.push.call_args[0]
    assert push_args[0] == branch_name
    instance.open_pr.assert_called_once()
    open_pr_kwargs = instance.open_pr.call_args.kwargs or {}
    open_pr_args = instance.open_pr.call_args.args
    def _pick2(name, idx):
        if name in open_pr_kwargs:
            return open_pr_kwargs[name]
        return open_pr_args[idx]
    title = _pick2("title", 0)
    body_text = _pick2("body", 1)
    head_branch = _pick2("head_branch", 2)
    base_branch = _pick2("base_branch", 3)
    assert "onboarding" in title
    assert "Tighten the welcome section" in title or "Tighten the welcome section" in body_text
    assert head_branch == branch_name
    assert base_branch == "main"
    assert "Opened by PolicyCodex on behalf of editor" in body_text
    # Call order: branch < commit < push < open_pr.
    branch_n = instance.branch.call_args_list[0]
    commit_n = instance.commit.call_args_list[0]
    push_n = instance.push.call_args_list[0]
    open_pr_n = instance.open_pr.call_args_list[0]
    # Use the mock's mock_calls index ordering on the parent.
    parent_calls = MockProvider.return_value.mock_calls
    method_names = [c[0] for c in parent_calls]
    assert method_names.index("branch") < method_names.index("commit") < method_names.index("push") < method_names.index("open_pr")


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
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = {"pr_number": 1, "url": "u", "state": "open"}
                    client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "T2", "body": "b2\n", "summary": ""},
                    )
    commit_call = instance.commit.call_args
    msg = commit_call.kwargs.get("message", commit_call.args[0] if commit_call.args else None)
    assert msg == "Update onboarding"


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
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([real_policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = {
                        "pr_number": 42,
                        "url": "https://github.com/example/diocese-policies/pull/42",
                        "state": "open",
                    }
                    response = client.post(
                        "/policies/onboarding/edit/",
                        data={"title": "T2", "body": "b2\n", "summary": "msg"},
                        follow=True,  # follow a redirect-to-success-page if used
                    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "https://github.com/example/diocese-policies/pull/42" in body
    assert "42" in body  # PR number visible somewhere
