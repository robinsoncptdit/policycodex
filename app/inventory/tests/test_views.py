"""DISC-12: /onboarding/inventory/ page renders and starts a run."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    User.objects.create_superuser("admin", "a@b.com", "pw")
    c = Client()
    c.login(username="admin", password="pw")
    return c


@pytest.mark.django_db
def test_get_creates_run_and_renders(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_INGEST_STAGING_ROOT", str(tmp_path / "stage"))
    stage = tmp_path / "stage" / "run-1"
    stage.mkdir(parents=True)
    (stage / "a.pdf").write_text("x")
    (stage / "b.pdf").write_text("y")
    session = logged_in_admin.session
    session["onboarding"] = {
        "current_step": "policy-documents",
        "completed": [
            "admin-account", "github-app", "llm-provider",
            "github-repo", "configuration", "retention-policy",
            "policy-documents",
        ],
        "data": {"policy-documents": {"run_id": "run-1", "stage_dir": str(stage)}},
    }
    session.save()
    with (
        patch("app.inventory.views.start_run") as start_run,
        patch("app.inventory.views._working_dir_or_fail", return_value=tmp_path / "wc"),
    ):
        r = logged_in_admin.get("/onboarding/inventory/")
    assert r.status_code == 200
    start_run.assert_called_once()
    from app.inventory.models import InventoryRun, InventoryItem
    assert InventoryRun.objects.count() == 1
    assert InventoryItem.objects.filter(source_filename="a.pdf").exists()
    assert InventoryItem.objects.filter(source_filename="b.pdf").exists()


@pytest.mark.django_db
def test_get_with_no_staged_files_redirects_to_policy_documents(logged_in_admin):
    """When the wizard's policy-documents state is missing, send the user back."""
    r = logged_in_admin.get("/onboarding/inventory/", follow=False)
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/policy-documents/")


@pytest.mark.django_db
def test_get_with_already_completed_run_redirects_to_catalog(logged_in_admin, tmp_path, monkeypatch):
    """If a run already completed, jump to /catalog/."""
    from app.inventory.models import InventoryRun
    monkeypatch.setenv("POLICYCODEX_INGEST_STAGING_ROOT", str(tmp_path / "stage"))
    session = logged_in_admin.session
    session["onboarding"] = {
        "current_step": "policy-documents",
        "completed": ["policy-documents"],
        "data": {"policy-documents": {"run_id": "x", "stage_dir": str(tmp_path / "stage" / "x")}},
    }
    session.save()
    InventoryRun.objects.create(status="completed", total=2, completed=2)
    r = logged_in_admin.get("/onboarding/inventory/", follow=False)
    assert r.status_code == 302
    assert r.url.endswith("/catalog/")
