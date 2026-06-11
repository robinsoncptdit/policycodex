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
