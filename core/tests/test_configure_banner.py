import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    # The seeded admin already exists; reuse it so we don't collide on UNIQUE.
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    """Provide a scratch credential store so tests that hit /settings/ views
    do not fail on the missing /data/.credential-key guard."""
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


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


def test_no_banner_on_settings_pages(client, admin):
    """The banner's Configure button would just re-link to a Settings
    panel — pointless when the user is already inside Settings."""
    client.force_login(admin)
    with patch("core.context_processors._safe_lifecycle_state") as m:
        from core.lifecycle import LifecycleState, ConfigureState
        m.return_value = LifecycleState(
            state=ConfigureState.NO_GITHUB_APP,
            next_url="/settings/github-app/",
            banner="Set up GitHub access in Settings → GitHub App.",
        )
        response = client.get("/settings/github-app/")
    assert b"configure-banner" not in response.content


def test_banner_still_shows_on_catalog(client, admin):
    """Sanity: suppression is scoped to /settings/, not blanket."""
    client.force_login(admin)
    with patch("core.context_processors._safe_lifecycle_state") as m:
        from core.lifecycle import LifecycleState, ConfigureState
        m.return_value = LifecycleState(
            state=ConfigureState.NO_GITHUB_APP,
            next_url="/settings/github-app/",
            banner="Set up GitHub access in Settings → GitHub App.",
        )
        response = client.get("/catalog/")
    assert b"configure-banner" in response.content


def test_banner_renders_progress(client, admin):
    from app.credentials import store
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    client.force_login(admin)
    response = client.get("/catalog/")
    body = response.content.decode()
    assert "1 of 4" in body or "1 / 4" in body
