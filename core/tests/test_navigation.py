import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.fixture(autouse=True)
def credential_env(tmp_path, monkeypatch):
    from app.credentials import store
    key_file = tmp_path / ".credential-key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_KEY_FILE", str(key_file))
    monkeypatch.setenv("POLICYCODEX_CREDENTIAL_STORE_FILE", str(tmp_path / ".credentials"))
    store._reset_cache()


@pytest.fixture
def editor(db):
    u = User.objects.create_user("ed", password="x")
    u.profile.must_change_password = False
    u.profile.save()
    u.groups.add(Group.objects.get(name="Editor"))
    return u


@pytest.fixture
def admin(db):
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    return u


def test_global_nav_present_on_catalog_for_editor(client, editor):
    client.force_login(editor)
    response = client.get("/catalog/")
    body = response.content
    assert b'href="/catalog/"' in body
    assert b'href="/inventory/"' in body
    assert b'>Catalog<' in body
    assert b'>Inventory<' in body


def test_global_nav_present_on_inventory_for_editor(client, editor):
    client.force_login(editor)
    response = client.get("/inventory/")
    body = response.content
    assert b'href="/catalog/"' in body
    assert b'href="/inventory/"' in body


def test_global_nav_includes_settings_for_admin(client, admin):
    client.force_login(admin)
    response = client.get("/settings/github-app/")
    body = response.content
    assert b'href="/settings/"' in body
    assert b'>Settings<' in body


def test_global_nav_hides_settings_for_editor(client, editor):
    client.force_login(editor)
    response = client.get("/catalog/")
    body = response.content
    assert b'>Settings<' not in body


def test_global_nav_absent_when_not_authenticated(client):
    response = client.get("/login/")
    assert b'href="/inventory/"' not in response.content


def test_navbar_has_no_leaked_template_comments(client, admin):
    # Regression: a multi-line {# #} comment in base.html's nav rendered as
    # literal text on every authenticated page, because Django's {# #} syntax
    # is single-line only. Multi-line developer notes must use {% comment %}.
    client.force_login(admin)
    body = client.get("/catalog/").content
    assert b"{#" not in body
    assert b"#}" not in body
    assert b"is_superuser" not in body
