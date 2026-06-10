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
                with patch("core.views.GitHubProvider"):
                    with patch(
                        "core.views.propose_change", return_value=fake_pr
                    ) as mock_propose:
                        resp = client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload, follow=True,
                        )
    assert resp.status_code == 200
    written = yaml.safe_load(policy.data_path.read_text())
    assert [c["id"] for c in written["classifications"]] == ["administrative", "financial", "legal"]
    assert written["classifications"][0]["name"] == "Administrative Records"
    assert written["retention_schedule"][0]["retention"] == "5 years"
    mock_propose.assert_called_once()
    kwargs = mock_propose.call_args.kwargs
    assert kwargs["branch_name"].startswith("policycodex/edit-document-retention-")
    assert kwargs["files"] == [policy.data_path]
    assert kwargs["default_branch"] == "main"
    assert "https://github.com/x/y/pull/31" in resp.content.decode()


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
                with patch("core.views.GitHubProvider"):
                    with patch(
                        "core.views.propose_change",
                        return_value={"pr_number": 1, "url": "u", "state": "open"},
                    ):
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
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change") as mock_propose:
                        resp = client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
                        mock_propose.assert_not_called()
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
                with patch("core.views.GitHubProvider"):
                    with patch(
                        "core.views.propose_change",
                        side_effect=RuntimeError("git push failed"),
                    ):
                        resp = client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Open PR" in body  # editor re-rendered, not a 500
    assert "couldn't" in body.lower() or "failed" in body.lower() or "error" in body.lower()


# APP-32: deprecated:true tombstone representation + soft-delete on DELETE.

_DEPRECATED_DATA_YAML = (
    "classifications:\n"
    "- id: administrative\n"
    "  name: Administrative\n"
    "- id: legacy-hr\n"
    "  name: Legacy HR Records\n"
    "  deprecated: true\n"
    "retention_schedule:\n"
    "- group: Administrative Records\n"
    "  type: General correspondence\n"
    "  retention: 3 years\n"
)


def _bundle_with_deprecated(tmp_path):
    """A bundle whose data.yaml carries a pre-existing deprecated classification."""
    policies_dir = tmp_path / "policies"
    bundle = policies_dir / "document-retention"
    bundle.mkdir(parents=True)
    (bundle / "policy.md").write_text(
        "---\ntitle: Document Retention Policy\nowner: CFO\n"
        "foundational: true\nprovides:\n- classifications\n- retention-schedule\n---\n\n# DRP\n",
        encoding="utf-8",
    )
    (bundle / "data.yaml").write_text(_DEPRECATED_DATA_YAML, encoding="utf-8")
    policy = LogicalPolicy(
        slug="document-retention", kind="bundle",
        policy_path=bundle / "policy.md", data_path=bundle / "data.yaml",
        frontmatter={"title": "Document Retention Policy", "owner": "CFO",
                     "foundational": True, "provides": ["classifications", "retention-schedule"]},
        body="# DRP\n", foundational=True,
        provides=("classifications", "retention-schedule"),
    )
    return policies_dir, policy


def test_get_renders_deprecated_classification_with_checkbox_checked(client, user, tmp_path):
    """The deprecated:true row round-trips into the rendered form as a checked checkbox."""
    client.force_login(user)
    _policies_dir, policy = _bundle_with_deprecated(tmp_path)
    with override_settings(POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
                           POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path)):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                resp = client.get("/policies/document-retention/foundational-edit/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="cls-1-deprecated"' in body
    legacy_row_idx = body.find('value="legacy-hr"')
    assert legacy_row_idx != -1
    deprecated_cb_idx = body.find('name="cls-1-deprecated"', legacy_row_idx)
    snippet = body[deprecated_cb_idx:deprecated_cb_idx + 200]
    assert "checked" in snippet, f"deprecated checkbox not rendered checked: {snippet!r}"


def test_post_delete_existing_classification_writes_soft_delete_tombstone(client, user, tmp_path):
    """DELETE on an existing classification row writes {id, name, deprecated: true} instead of dropping."""
    client.force_login(user)
    _policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative"},
            {"id": "financial", "name": "Financial", "DELETE": "on"},
        ],
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change",
                               return_value={"pr_number": 1, "url": "u", "state": "open"}):
                        client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
    written = yaml.safe_load(policy.data_path.read_text())
    ids = [c["id"] for c in written["classifications"]]
    assert ids == ["administrative", "financial"]
    fin = written["classifications"][1]
    assert fin == {"id": "financial", "name": "Financial", "deprecated": True}
    assert "deprecated" not in written["classifications"][0]


def test_post_delete_new_extra_classification_drops_it(client, user, tmp_path):
    """DELETE on a brand-new 'extra' classification row drops it entirely (never existed)."""
    client.force_login(user)
    _policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative"},
            {"id": "financial", "name": "Financial"},
        ],
        add_classification={"id": "legal", "name": "Legal", "DELETE": "on"},
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change",
                               return_value={"pr_number": 1, "url": "u", "state": "open"}):
                        client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
    written = yaml.safe_load(policy.data_path.read_text())
    ids = [c["id"] for c in written["classifications"]]
    assert ids == ["administrative", "financial"]
    for c in written["classifications"]:
        assert "deprecated" not in c


def test_post_checking_deprecated_without_delete_writes_deprecated_flag(client, user, tmp_path):
    """Checking the `deprecated` checkbox on a live row writes deprecated: true (explicit flip)."""
    client.force_login(user)
    _policies_dir, policy = _bundle_on_disk(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative", "deprecated": "on"},
            {"id": "financial", "name": "Financial"},
        ],
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
            {"group": "Financial Records", "type": "Audited statements",
             "retention": "Permanent"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change",
                               return_value={"pr_number": 1, "url": "u", "state": "open"}):
                        client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
    written = yaml.safe_load(policy.data_path.read_text())
    assert written["classifications"][0] == {
        "id": "administrative", "name": "Administrative", "deprecated": True,
    }


def test_post_round_trip_preserves_pre_existing_deprecated_row(client, user, tmp_path):
    """Editing other fields leaves a pre-existing deprecated row unchanged (still deprecated)."""
    client.force_login(user)
    _policies_dir, policy = _bundle_with_deprecated(tmp_path)
    payload = _post_payload(
        classifications=[
            {"id": "administrative", "name": "Administrative Records"},
            {"id": "legacy-hr", "name": "Legacy HR Records", "deprecated": "on"},
        ],
        retention=[
            {"group": "Administrative Records", "type": "General correspondence",
             "retention": "3 years"},
        ],
    )
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://github.com/example/diocese-policies.git",
        POLICYCODEX_WORKING_COPY_ROOT=str(tmp_path),
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([policy])
                with patch("core.views.GitHubProvider"):
                    with patch("core.views.propose_change",
                               return_value={"pr_number": 1, "url": "u", "state": "open"}):
                        client.post(
                            "/policies/document-retention/foundational-edit/",
                            data=payload,
                        )
    written = yaml.safe_load(policy.data_path.read_text())
    assert written["classifications"][0] == {"id": "administrative", "name": "Administrative Records"}
    assert written["classifications"][1] == {
        "id": "legacy-hr", "name": "Legacy HR Records", "deprecated": True,
    }
