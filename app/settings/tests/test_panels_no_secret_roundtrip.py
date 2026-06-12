import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

User = get_user_model()
_PEM = "-----BEGIN PRIVATE KEY-----\nABCDEFGHIJKL\n-----END PRIVATE KEY-----"
_API_KEY = "sk-ant-this-is-a-real-looking-key-value-1234567890"


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


def test_llm_provider_does_not_re_render_saved_api_key(client, admin):
    from app.credentials import store
    store.set("llm.provider", "claude")
    store.set("llm.claude.api_key", _API_KEY)
    client.force_login(admin)
    response = client.get("/settings/llm-provider/")
    body = response.content.decode()
    assert _API_KEY not in body, (
        "Saved API key must not be rendered back into the form. "
        "Found in response body — secret leak."
    )
    # Field type should be password, not text.
    assert 'name="api_key"' in body
    api_field_idx = body.index('name="api_key"')
    surrounding = body[max(0, api_field_idx - 200):api_field_idx + 200]
    assert 'type="password"' in surrounding, (
        f"api_key field should be type=password; got: {surrounding}"
    )


def test_github_app_does_not_re_render_saved_pem(client, admin):
    from app.credentials import store
    store.set("github_app.app_id", "123")
    store.set("github_app.installation_id", "456")
    store.set("github_app.private_key_pem", _PEM)
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    body = response.content.decode()
    assert _PEM not in body, (
        "Saved PEM must not be rendered back into the textarea."
    )
    # App ID + Installation ID are NOT secrets and CAN be re-rendered.
    assert "123" in body
    assert "456" in body


def test_llm_provider_api_key_autocomplete_off(client, admin):
    client.force_login(admin)
    response = client.get("/settings/llm-provider/")
    body = response.content.decode()
    api_field_idx = body.index('name="api_key"')
    surrounding = body[max(0, api_field_idx - 200):api_field_idx + 200]
    assert 'autocomplete="new-password"' in surrounding


def test_github_app_pem_textarea_autocomplete_off(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    body = response.content.decode()
    pem_field_idx = body.index('name="private_key_pem"')
    surrounding = body[max(0, pem_field_idx - 200):pem_field_idx + 400]
    assert 'autocomplete="new-password"' in surrounding
