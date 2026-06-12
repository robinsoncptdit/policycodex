import pytest
from unittest.mock import patch, MagicMock
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


def test_sync_calls_working_copy_manager_and_redirects(client, editor):
    client.force_login(editor)
    with patch("core.views.WorkingCopyManager") as mock_mgr, \
         patch("core.views.load_working_copy_config") as mock_cfg, \
         patch("core.views.GitHubProvider"):
        instance = mock_mgr.return_value
        instance.sync.return_value = None
        response = client.post("/catalog/sync/")
    assert response.status_code == 302
    assert response.url == "/catalog/"
    instance.sync.assert_called_once()


def test_sync_swallows_failure_and_redirects_with_message(client, editor, tmp_path):
    client.force_login(editor)
    with patch("core.views.WorkingCopyManager") as mock_mgr, \
         patch("core.views.load_working_copy_config") as mock_cfg, \
         patch("core.views.GitHubProvider"):
        # Point working_dir at a real but empty tmp dir so catalog renders
        # the empty-onboarding state (no policies/ subdir).
        mock_cfg.return_value.working_dir = tmp_path
        instance = mock_mgr.return_value
        instance.sync.side_effect = RuntimeError("github 404")
        response = client.post("/catalog/sync/", follow=True)
    # Final destination is the catalog; user sees a messages.error.
    assert response.status_code == 200
    assert b"could not sync" in response.content.lower()


def test_get_method_not_allowed(client, editor):
    client.force_login(editor)
    response = client.get("/catalog/sync/")
    assert response.status_code == 405


def test_sync_writes_last_sync_marker(client, editor, tmp_path):
    """After a successful sync the working copy carries a marker file
    with an ISO 8601 timestamp."""
    from unittest.mock import patch, MagicMock
    client.force_login(editor)
    cfg = MagicMock()
    cfg.working_dir = tmp_path
    cfg.branch = "main"
    with patch("core.views.WorkingCopyManager") as mock_mgr, \
         patch("core.views.load_working_copy_config", return_value=cfg), \
         patch("core.views.GitHubProvider"):
        mock_mgr.return_value.sync.return_value = None
        client.post("/catalog/sync/")
    marker = tmp_path / ".policycodex" / "last_sync.json"
    assert marker.exists()
    import json
    payload = json.loads(marker.read_text())
    assert "iso" in payload
    assert payload["iso"].startswith("20")


def test_catalog_shows_last_synced_text_when_marker_exists(client, editor, tmp_path):
    from unittest.mock import patch, MagicMock
    # Pre-create the marker but NOT the policies/ dir, so catalog falls
    # through to the empty-state branch after reading the marker.
    cfg_dir = tmp_path / ".policycodex"
    cfg_dir.mkdir()
    (cfg_dir / "last_sync.json").write_text('{"iso": "2026-06-12T14:30:00Z"}')
    # policies/ is intentionally absent so catalog renders empty-state.
    client.force_login(editor)
    with patch("core.views.load_working_copy_config") as mock_cfg:
        mock_cfg.return_value.working_dir = tmp_path
        response = client.get("/catalog/")
    assert b"Last synced" in response.content
