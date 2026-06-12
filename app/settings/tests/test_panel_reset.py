import pytest
from pathlib import Path
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


def test_get_renders_three_actions(client, admin):
    client.force_login(admin)
    response = client.get("/settings/reset/")
    assert response.status_code == 200
    assert b"Clear credential store" in response.content
    assert b"Disconnect everything" in response.content
    assert b"Full factory reset" in response.content


def test_clear_credentials_wipes_store(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("llm.provider", "claude")
    response = client.post("/settings/reset/", {
        "action": "clear_credentials",
        "confirm_token": "CLEAR",
    })
    store._reset_cache()
    assert not store.has("llm.provider")


def test_clear_credentials_wrong_token_no_op(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("llm.provider", "claude")
    response = client.post("/settings/reset/", {
        "action": "clear_credentials",
        "confirm_token": "WRONG",
    })
    assert store.has("llm.provider")


def test_full_factory_reset_requires_long_token(client, admin):
    client.force_login(admin)
    from app.credentials import store
    store.set("llm.provider", "claude")
    other = User.objects.create_user("alice", password="x")
    response = client.post("/settings/reset/", {
        "action": "factory_reset",
        "confirm_token": "WRONG",
    })
    assert User.objects.filter(username="alice").exists()
    assert store.has("llm.provider")
    response = client.post("/settings/reset/", {
        "action": "factory_reset",
        "confirm_token": "RESET POLICYCODEX",
    })
    store._reset_cache()
    assert not User.objects.filter(username="alice").exists()
    assert User.objects.filter(username="admin").exists()  # the acting admin survives
    assert not store.has("llm.provider")
