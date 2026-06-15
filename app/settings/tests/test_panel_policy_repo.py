import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
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


def test_get_renders_form(client, admin):
    client.force_login(admin)
    response = client.get("/settings/policy-repo/")
    assert response.status_code == 200
    assert b"Repository URL" in response.content


def test_test_endpoint_ok(client, admin):
    client.force_login(admin)
    with patch("app.settings.panels.policy_repo._git_ls_remote", return_value=True):
        response = client.post("/htmx/settings/policy-repo/test/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
    assert b'data-state="ok"' in response.content


def test_save_writes_to_store_and_syncs(client, admin):
    client.force_login(admin)
    from app.credentials import store
    with patch("app.settings.panels.policy_repo._git_ls_remote", return_value=True), \
         patch("app.settings.panels.policy_repo.WorkingCopyManager") as mgr, \
         patch("app.settings.panels.policy_repo.GitHubProvider"):
        instance = mgr.return_value
        client.post("/htmx/settings/policy-repo/test/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
        response = client.post("/settings/policy-repo/", {
            "repo_url": "https://github.com/diocese/policies",
            "branch": "main",
        })
    assert store.get("policy_repo.url") == "https://github.com/diocese/policies"
    assert store.get("policy_repo.branch") == "main"
    instance.sync.assert_called_once()


def test_disconnect_clears_store_and_removes_working_copy(client, admin, tmp_path, monkeypatch):
    client.force_login(admin)
    from app.credentials import store
    monkeypatch.setenv("POLICYCODEX_WORKING_COPY_ROOT", str(tmp_path / "wc"))
    (tmp_path / "wc").mkdir()
    (tmp_path / "wc" / "policies-repo").mkdir()
    store.set("policy_repo.url", "https://github.com/diocese/policies")
    store.set("policy_repo.branch", "main")
    response = client.post("/settings/policy-repo/", {
        "action": "disconnect",
        "confirm_token": "DISCONNECT",
    })
    assert not store.has("policy_repo.url")
    assert not (tmp_path / "wc" / "policies-repo").exists()


def test_policy_repo_panel_has_intro(client, admin):
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/x/y")
    store.set("policy_repo.branch", "main")
    client.force_login(admin)
    response = client.get("/settings/policy-repo/")
    body = response.content.decode()
    # An intro paragraph appears before the form.
    body_after_title = body[body.index("<h1"):]
    assert "<p" in body_after_title[:500]


from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile


def _login_admin(client):
    User = get_user_model()
    u = User.objects.get(username="admin")
    u.profile.must_change_password = False
    u.profile.save()
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_upload_retention_requires_configured_repo(client):
    _login_admin(client)
    from app.credentials import store
    store._reset_cache()  # no policy_repo.url
    upload = SimpleUploadedFile("r.txt", b"text", content_type="text/plain")
    resp = client.post("/settings/policy-repo/", {"action": "upload_retention", "retention_document": upload})
    assert b"Connect and initialize a policy repository first." in resp.content


@pytest.mark.django_db
def test_upload_retention_rejects_no_file(client, tmp_path, monkeypatch):
    _login_admin(client)
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/d/r")
    store.set("policy_repo.branch", "main")
    resp = client.post("/settings/policy-repo/", {"action": "upload_retention"})
    assert b"Choose a retention policy document" in resp.content


@pytest.mark.django_db
def test_upload_retention_rejects_bad_suffix(client):
    _login_admin(client)
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/d/r")
    store.set("policy_repo.branch", "main")
    upload = SimpleUploadedFile("r.exe", b"x", content_type="application/octet-stream")
    resp = client.post("/settings/policy-repo/", {"action": "upload_retention", "retention_document": upload})
    assert b"Unsupported file type" in resp.content


@pytest.mark.django_db
def test_upload_retention_happy_path_calls_scaffolder(client):
    _login_admin(client)
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/d/r")
    store.set("policy_repo.branch", "main")
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
    with patch("app.settings.panels.policy_repo.scaffold_retention_bundle") as scaffold, \
         patch("app.settings.panels.policy_repo.ClaudeProvider"), \
         patch("app.settings.panels.policy_repo.GitHubProvider"), \
         patch("app.settings.panels.policy_repo.load_working_copy_config") as cfg:
        from types import SimpleNamespace
        cfg.return_value = SimpleNamespace(working_dir="/tmp/wc", branch="main")
        scaffold.return_value = {"url": "https://github.com/d/r/pull/12", "pr_number": 12}
        resp = client.post("/settings/policy-repo/",
                           {"action": "upload_retention", "retention_document": upload})
    # The panel's job: write the upload to a temp file and thread config +
    # author identity into the scaffolder. Verify that wiring, not just .called.
    assert scaffold.call_count == 1
    kwargs = scaffold.call_args.kwargs
    assert kwargs["working_dir"] == "/tmp/wc"
    assert kwargs["default_branch"] == "main"
    assert kwargs["document_path"].name == "retention.pdf"
    assert b"Retention policy parsed" in resp.content
    # The PR link renders from pr_url now that the template (Task 3) is in place.
    assert b"pull/12" in resp.content


@pytest.mark.django_db
def test_upload_form_present_when_repo_configured(client):
    _login_admin(client)
    from app.credentials import store
    store.set("policy_repo.url", "https://github.com/d/r")
    store.set("policy_repo.branch", "main")
    resp = client.get("/settings/policy-repo/")
    body = resp.content
    assert b'name="retention_document"' in body
    assert b'enctype="multipart/form-data"' in body
    assert b'value="upload_retention"' in body


@pytest.mark.django_db
def test_upload_form_absent_when_repo_not_configured(client):
    _login_admin(client)
    from app.credentials import store
    store._reset_cache()  # no policy_repo.url -> the form is gated off
    resp = client.get("/settings/policy-repo/")
    assert b'name="retention_document"' not in resp.content
