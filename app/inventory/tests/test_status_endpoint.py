"""HTMX polling endpoint returns the status fragment for all lifecycle states."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    admin = User.objects.get(username="admin")
    admin.profile.must_change_password = False
    admin.profile.save()
    c = Client()
    c.force_login(admin)
    return c


@pytest.mark.django_db
def test_status_fragment_returns_html(logged_in_admin):
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(status="running", total=2, completed=1)
    InventoryItem.objects.create(run=run, source_filename="a.pdf", status="done", title="A")
    InventoryItem.objects.create(run=run, source_filename="b.pdf", status="extracting")
    r = logged_in_admin.get(f"/htmx/inventory/status/?run={run.pk}")
    assert r.status_code == 200
    assert b"1 of 2" in r.content
    assert b"a.pdf" in r.content


@pytest.mark.django_db
def test_completed_run_renders_success_banner(logged_in_admin):
    from app.inventory.models import InventoryRun
    run = InventoryRun.objects.create(status="completed", total=2, completed=2, pr_url="https://github.com/x/y/pull/1")
    r = logged_in_admin.get(f"/htmx/inventory/status/?run={run.pk}")
    assert r.status_code == 200
    assert b"Most recent extraction" in r.content
    assert b"pull/1" in r.content


@pytest.mark.django_db
def test_missing_run_returns_404(logged_in_admin):
    r = logged_in_admin.get("/htmx/inventory/status/?run=9999999")
    assert r.status_code == 404


@pytest.mark.django_db
def test_failed_run_renders_failure_summary(logged_in_admin):
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(status="failed", total=2, completed=1, failed=1, pr_error="LLM provider 401")
    InventoryItem.objects.create(run=run, source_filename="a.pdf", status="done", title="A")
    InventoryItem.objects.create(run=run, source_filename="b.pdf", status="failed", error_message="image-only PDF")
    r = logged_in_admin.get(f"/htmx/inventory/status/?run={run.pk}")
    assert r.status_code == 200
    # No HX-Redirect on failure; user sees the cards + a failure banner.
    assert "HX-Redirect" not in r
    assert b"image-only PDF" in r.content
