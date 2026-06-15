import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.fixture
def editor(db):
    u = User.objects.create_user("ed", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Editor"))
    return u


def test_empty_state_renders_only_bucket(client, editor):
    client.force_login(editor)
    response = client.get("/inventory/")
    assert response.status_code == 200
    assert b"Drop your policy documents" in response.content
    # No cards visible.
    assert b"Most recent extraction" not in response.content


def test_active_state_renders_cards_and_disabled_bucket(client, editor):
    from app.inventory.models import InventoryRun, InventoryItem
    run = InventoryRun.objects.create(status="running", total=2)
    InventoryItem.objects.create(run=run, source_filename="a.pdf", status="extracting")
    InventoryItem.objects.create(run=run, source_filename="b.pdf", status="pending")
    client.force_login(editor)
    response = client.get("/inventory/")
    assert b"a.pdf" in response.content
    assert b"Extraction in progress" in response.content


def test_completed_state_shows_pr_link(client, editor):
    from app.inventory.models import InventoryRun
    InventoryRun.objects.create(
        status="completed", total=2, completed=2,
        pr_url="https://github.com/x/y/pull/42",
    )
    client.force_login(editor)
    response = client.get("/inventory/")
    assert b"Most recent extraction" in response.content
    assert b"pull/42" in response.content


def test_failed_state_shows_retry(client, editor):
    from app.inventory.models import InventoryRun
    InventoryRun.objects.create(status="failed", total=2, pr_error="LLM 401")
    client.force_login(editor)
    response = client.get("/inventory/")
    assert b"Retry whole run" in response.content
    assert b"LLM 401" in response.content


def test_viewer_denied(client, db):
    u = User.objects.create_user("v", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Viewer"))
    client.force_login(u)
    response = client.get("/inventory/")
    assert response.status_code == 403


def test_upload_bucket_is_wired_for_client_js(client, editor):
    """The bucket carries the DOM hooks and loads the upload JS so
    drag-and-drop and the picker actually submit the form."""
    client.force_login(editor)
    response = client.get("/inventory/")
    assert response.status_code == 200
    body = response.content
    # Stable hooks the JS targets.
    assert b'id="bucket-dropzone"' in body
    assert b'id="bucket-input"' in body
    assert b'id="add-policies"' in body
    # The client behavior script is loaded on this page.
    assert b"inventory-upload.js" in body
