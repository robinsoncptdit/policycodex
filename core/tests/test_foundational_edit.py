"""Tests for the foundational typed-table editor view (APP-25)."""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from ingest.policy_reader import LogicalPolicy

User = get_user_model()

DATA_YAML = (
    "classifications:\n"
    "- id: administrative\n"
    "  name: Administrative\n"
    "- id: financial\n"
    "  name: Financial\n"
    "retention_schedule:\n"
    "- group: Administrative Records\n"
    "  type: General correspondence\n"
    "  retention: 3 years\n"
    "- group: Financial Records\n"
    "  type: Audited statements\n"
    "  retention: Permanent\n"
)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="editor", password="hunter2hunter2",
        email="editor@example.com", first_name="Pat", last_name="Editor",
    )


def _bundle_on_disk(tmp_path):
    """Write a real document-retention bundle; return (policies_dir, LogicalPolicy)."""
    policies_dir = tmp_path / "policies"
    bundle = policies_dir / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(
        "---\ntitle: Document Retention Policy\nowner: CFO\n"
        "foundational: true\nprovides:\n- classifications\n- retention-schedule\n---\n\n# DRP\n",
        encoding="utf-8",
    )
    (bundle / "data.yaml").write_text(DATA_YAML, encoding="utf-8")
    policy = LogicalPolicy(
        slug="document-retention", kind="bundle",
        policy_path=bundle / "policy.md", data_path=bundle / "data.yaml",
        frontmatter={"title": "Document Retention Policy", "owner": "CFO",
                     "foundational": True, "provides": ["classifications", "retention-schedule"]},
        body="# DRP\n", foundational=True,
        provides=("classifications", "retention-schedule"),
    )
    return policies_dir, policy


def test_url_resolves():
    assert reverse("foundational_edit", kwargs={"slug": "document-retention"}) == \
        "/policies/document-retention/foundational-edit/"


def test_requires_login(client):
    resp = client.get("/policies/document-retention/foundational-edit/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")


def test_404_when_slug_missing(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                resp = client.get("/policies/not-here/foundational-edit/")
    assert resp.status_code == 404


def test_non_foundational_redirects_to_flat_editor(client, user, tmp_path):
    client.force_login(user)
    flat = LogicalPolicy(
        slug="whistleblower", kind="flat", policy_path=Path("/tmp/p/whistleblower.md"),
        data_path=None, frontmatter={"title": "Whistleblower"}, body="b",
        foundational=False, provides=(),
    )
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([flat])
                resp = client.get("/policies/whistleblower/foundational-edit/")
    assert resp.status_code == 302
    assert resp.url == "/policies/whistleblower/edit/"


def test_get_renders_editable_tables_prepopulated(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                resp = client.get("/policies/document-retention/foundational-edit/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'value="administrative"' in body
    assert 'value="Administrative"' in body
    assert 'value="Audited statements"' in body
    assert 'value="Permanent"' in body
    assert "csrfmiddlewaretoken" in body
    assert 'name="cls-TOTAL_FORMS"' in body
    assert 'name="ret-TOTAL_FORMS"' in body
