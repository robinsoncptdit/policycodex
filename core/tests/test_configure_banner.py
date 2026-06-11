import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    # The seeded admin already exists; reuse it so we don't collide on UNIQUE.
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


def test_no_gh_app_renders_banner_on_catalog(client, admin):
    client.force_login(admin)
    with patch("core.context_processors._safe_lifecycle_state") as m:
        from core.lifecycle import LifecycleState, ConfigureState
        m.return_value = LifecycleState(
            state=ConfigureState.NO_GITHUB_APP,
            next_url="/settings/github-app/",
            banner="Set up GitHub access in Settings → GitHub App.",
        )
        response = client.get("/catalog/")
    assert b"Set up GitHub access" in response.content


def test_ready_state_no_banner_on_catalog(client, admin):
    client.force_login(admin)
    with patch("core.context_processors._safe_lifecycle_state") as m:
        from core.lifecycle import LifecycleState, ConfigureState
        m.return_value = LifecycleState(
            state=ConfigureState.READY, next_url="/catalog/", banner=None,
        )
        response = client.get("/catalog/")
    assert b"Set up GitHub access" not in response.content
    assert b"Connect your AI provider" not in response.content


def test_banner_absent_when_not_authenticated(client):
    response = client.get("/login/")
    # Banner only renders for authenticated users; login page is public.
    assert b"configure-banner" not in response.content
