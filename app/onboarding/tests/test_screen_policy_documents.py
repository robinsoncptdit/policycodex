"""DISC-10: Screen 7 policy-documents drag-and-drop upload."""
from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    User.objects.create_superuser("admin", "a@b.com", "pw")
    c = Client()
    c.login(username="admin", password="pw")
    # Pre-seed wizard state so gating Signal 3 allows reaching policy-documents (index 6)
    session = c.session
    session["onboarding"] = {
        "current_step": "policy-documents",
        "completed": [
            "admin-account", "github-app", "llm-provider",
            "github-repo", "configuration", "retention-policy",
        ],
        "data": {},
    }
    session.save()
    return c


@pytest.fixture(autouse=True)
def working_copy_present(tmp_path, monkeypatch):
    """Gating Signal 2 requires _working_copy_dir().exists() for policy-documents."""
    wd = tmp_path / "wc"
    wd.mkdir()
    monkeypatch.setattr("app.onboarding.views._working_copy_dir", lambda: wd)


def test_get_renders_drop_zone(logged_in_admin):
    r = logged_in_admin.get("/onboarding/policy-documents/")
    assert r.status_code == 200
    assert b"Drop your policy documents" in r.content


def test_post_three_files_stages_and_redirects(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_INGEST_STAGING_ROOT", str(tmp_path / "stage"))
    f1 = SimpleUploadedFile("hr-001.pdf", b"%PDF-1.4 fake")
    f2 = SimpleUploadedFile("eth-002.docx", b"PK\x03\x04 fake docx")
    f3 = SimpleUploadedFile("note.md", b"# Some policy")
    r = logged_in_admin.post(
        "/onboarding/policy-documents/",
        {"action": "continue", "files": [f1, f2, f3]},
    )
    # The redirect target is the inventory page.
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/inventory/")
    # All three files landed under a single run-id staging dir.
    staged = list((tmp_path / "stage").rglob("*"))
    assert any(p.name == "hr-001.pdf" for p in staged)
    assert any(p.name == "eth-002.docx" for p in staged)
    assert any(p.name == "note.md" for p in staged)


def test_disallowed_extension_returns_error(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_INGEST_STAGING_ROOT", str(tmp_path / "stage"))
    bad = SimpleUploadedFile("trojan.exe", b"MZ fake")
    r = logged_in_admin.post(
        "/onboarding/policy-documents/",
        {"action": "continue", "files": [bad]},
    )
    assert r.status_code == 200
    assert b"Unsupported file" in r.content


def test_oversized_file_returns_error(logged_in_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("POLICYCODEX_INGEST_STAGING_ROOT", str(tmp_path / "stage"))
    big = SimpleUploadedFile("big.pdf", b"X" * (26 * 1024 * 1024))  # 26MB
    r = logged_in_admin.post(
        "/onboarding/policy-documents/",
        {"action": "continue", "files": [big]},
    )
    assert r.status_code == 200
    assert b"too large" in r.content
