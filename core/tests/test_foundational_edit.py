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


def _formset_post(prefix, rows, extra=None):
    """Build management-form + per-row POST data for a formset.

    rows: list of dicts (existing/edited rows, in order). A row dict may
    include "DELETE": "on". `extra`: an optional dict for the trailing
    add-row (omit to leave it blank).
    """
    total = len(rows) + 1  # one extra add-row form
    data = {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(len(rows)),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for k, v in row.items():
            data[f"{prefix}-{i}-{k}"] = v
    extra = extra or {}
    for k, v in extra.items():
        data[f"{prefix}-{len(rows)}-{k}"] = v
    return data


def _post_payload(*, classifications, retention, add_classification=None, summary="msg"):
    data = {}
    data.update(_formset_post("cls", classifications, extra=add_classification))
    data.update(_formset_post("ret", retention))
    data["summary"] = summary
    return data


def test_post_valid_writes_data_yaml_and_opens_pr(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    fake_pr = {"pr_number": 31, "url": "https://github.com/x/y/pull/31", "state": "open"}
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative Records"},  # renamed
            {"id": "financial", "name": "Financial"},
        ],
        add_classification={"id": "legal", "name": "Legal"},  # added
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "5 years"},  # retention edited 3->5 years
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.open_pr.return_value = fake_pr
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload, follow=True,
                    )
    assert resp.status_code == 200
    written = yaml.safe_load(policy.data_path.read_text())
    assert [c["id"] for c in written["classifications"]] == ["administrative", "financial", "legal"]
    assert written["classifications"][0]["name"] == "Administrative Records"
    assert written["retention_schedule"][0]["retention"] == "5 years"
    instance.branch.assert_called_once()
    assert instance.branch.call_args[0][0].startswith("policycodex/edit-document-retention-")
    commit_call = instance.commit.call_args
    files = commit_call.kwargs.get("files", commit_call.args[1] if len(commit_call.args) > 1 else None)
    assert files == [policy.data_path]
    instance.push.assert_called_once()
    instance.open_pr.assert_called_once()
    assert "https://github.com/x/y/pull/31" in resp.content.decode()
    method_names = [c[0] for c in MockProvider.return_value.mock_calls]
    assert method_names.index("branch") < method_names.index("commit") \
        < method_names.index("push") < method_names.index("open_pr")


def test_post_delete_row_drops_it_from_data_yaml(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative"},
            {"id": "financial", "name": "Financial"},
        ],
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent", "DELETE": "on"},  # delete this row
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    MockProvider.return_value.open_pr.return_value = {
                        "pr_number": 1, "url": "u", "state": "open"}
                    client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
    written = yaml.safe_load(policy.data_path.read_text())
    types = [r["type"] for r in written["retention_schedule"]]
    assert types == ["General correspondence"]  # the deleted row is gone


def test_post_invalid_formset_rerenders_without_calling_provider(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[{"id": "administrative", "name": "Administrative"}],
        retention=[{"group": "G", "type": "T", "retention": ""}],  # blank required -> invalid
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
                    MockProvider.return_value.branch.assert_not_called()
    assert resp.status_code == 200
    assert "Open PR" in resp.content.decode()  # re-rendered editor


def test_post_provider_failure_rerenders_with_error(client, user, tmp_path):
    client.force_login(user)
    policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[{"id": "administrative", "name": "Administrative"}],
        retention=[{"group": "G", "type": "T", "retention": "3 years"}],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider") as MockProvider:
                    instance = MockProvider.return_value
                    instance.branch.side_effect = RuntimeError("git branch failed")
                    resp = client.post(
                        "/policies/document-retention/foundational-edit/",
                        data=payload,
                    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Open PR" in body  # editor re-rendered, not a 500
    assert "couldn't" in body.lower() or "failed" in body.lower() or "error" in body.lower()
