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
