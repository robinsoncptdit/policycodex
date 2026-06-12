import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin(db):
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


def test_left_rail_shows_no_checks_when_nothing_configured(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    body = response.content.decode()
    assert "GitHub App" in body
    # No panel has a check yet.
    assert 'data-configured="true"' not in body


def test_left_rail_shows_check_after_save(client, admin):
    from app.credentials import store
    store.set("github_app.app_id", "1")
    store.set("github_app.installation_id", "2")
    store.set("github_app.private_key_pem", "PEM")
    client.force_login(admin)
    response = client.get("/settings/llm-provider/")
    body = response.content.decode()
    gh_idx = body.index("GitHub App")
    surrounding = body[max(0, gh_idx - 400):gh_idx + 200]
    assert 'data-configured="true"' in surrounding
