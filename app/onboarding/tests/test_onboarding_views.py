"""Tests for the onboarding wizard views (APP-08)."""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin", password="secret")


# A valid github-repo form payload, for tests that POST `continue` past step 1.
GITHUB_REPO_CONTINUE = {
    "action": "continue",
    "mode": "connect",
    "repo_url": "https://github.com/acme/policies",
    "branch": "main",
}


def test_urls_resolve():
    assert reverse("onboarding") == "/onboarding/"
    assert reverse("onboarding_step", kwargs={"step": "github-repo"}) == "/onboarding/github-repo/"


def test_onboarding_requires_login(client):
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
    # The per-step view is guarded too.
    step_resp = client.get("/onboarding/github-repo/")
    assert step_resp.status_code == 302
    assert step_resp.url.startswith("/login/")


def test_root_redirects_to_first_step_when_fresh(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_get_step_renders_title_and_indicator(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "GitHub repository" in body
    assert "Step 1 of 7" in body


def test_unknown_step_returns_404(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/not-a-step/")
    assert resp.status_code == 404


def test_ahead_jump_is_gated(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/versioning/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_continue_advances_and_marks_complete(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    assert client.get("/onboarding/").url == "/onboarding/address-scheme/"


def test_back_goes_to_previous_step(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    resp = client.post("/onboarding/address-scheme/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_back_on_first_step_is_noop_redirect(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-repo/"


def test_save_exit_redirects_to_catalog(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", {"action": "save_exit"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_can_revisit_completed_step_without_trapping(client, user):
    client.force_login(user)
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert client.get("/onboarding/github-repo/").status_code == 200
    assert client.get("/onboarding/address-scheme/").status_code == 200


def test_last_step_continue_completes_and_redirects_to_catalog(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_github_repo_get_renders_form(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Mode radio + the connect URL field render.
    assert 'name="mode"' in body
    assert 'name="repo_url"' in body


def test_github_repo_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    # Missing repo_url for connect mode -> invalid.
    resp = client.post("/onboarding/github-repo/", {"action": "continue", "mode": "connect", "branch": "main"})
    assert resp.status_code == 200  # re-rendered, not redirected
    # Still on github-repo (not advanced); the step is not marked complete.
    assert client.get("/onboarding/").url == "/onboarding/github-repo/"


def test_github_repo_valid_continue_persists_and_advances(client, user):
    client.force_login(user)
    resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/address-scheme/"
    # The captured value is persisted and pre-populates a return visit.
    back = client.get("/onboarding/github-repo/")
    assert "https://github.com/acme/policies" in back.content.decode()


def test_no_form_step_still_advances_on_bare_continue(client, user):
    """Regression: a step with no registered form keeps the no-op continue."""
    client.force_login(user)
    # Advance past the form step first.
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    # address-scheme has no form; a bare continue advances.
    resp = client.post("/onboarding/address-scheme/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/versioning/"


# Steps 1-6 payloads to reach screen 7. Only github-repo has a real form.
def _advance_to_retention_policy(client):
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    for slug in ["address-scheme", "versioning", "reviewer-roles", "retention", "llm-provider"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})


FAKE_BUNDLE = {
    "classifications": [
        {"id": "administrative", "name": "Administrative"},
        {"id": "financial", "name": "Financial"},
    ],
    "classifications_confidence": "high",
    "retention_schedule": [
        {"group": "Administrative Records", "type": "Correspondence", "retention": "3 years"},
    ],
    "retention_schedule_confidence": "medium",
}


@pytest.fixture
def working_copy(settings, tmp_path):
    settings.POLICYCODEX_POLICY_REPO_URL = "https://github.com/acme/policies.git"
    settings.POLICYCODEX_WORKING_COPY_ROOT = str(tmp_path)
    # repo name "policies" -> working_dir = tmp_path/policies; the diocese repo
    # holds policies under a top-level policies/ dir (matches core/views.py),
    # so the policies root is working_dir/policies = tmp_path/policies/policies.
    policies_dir = tmp_path / "policies" / "policies"
    policies_dir.mkdir(parents=True)
    return policies_dir


@pytest.fixture
def stub_extraction(monkeypatch):
    """Avoid network + Anthropic() init; return a canned bundle and PDF text."""
    from app.onboarding import retention_policy as rp
    monkeypatch.setattr(rp, "extract_text", lambda path: "FAKE PDF TEXT")
    monkeypatch.setattr(rp, "extract_retention_bundle", lambda provider, text: FAKE_BUNDLE)
    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())


def test_screen7_get_shows_upload_form(client, user, working_copy):
    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.get("/onboarding/retention-policy/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'enctype="multipart/form-data"' in body
    assert 'name="pdf_file"' in body
    assert "Step 7 of 7" in body


def test_screen7_extract_shows_readonly_review(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Administrative" in body
    assert "2 classifications" in body       # count surfaced (truncation visibility)
    assert "1 retention" in body
    assert 'value="accept"' in body
    assert 'value="reupload"' in body


def test_screen7_extract_failure_rerenders_upload_with_error(client, user, working_copy, monkeypatch):
    """A corrupt PDF / provider outage must degrade to a friendly re-prompt, not 500."""
    from app.onboarding import retention_policy as rp

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())

    def _boom(path):
        raise ValueError("corrupt pdf bytes")

    monkeypatch.setattr(rp, "extract_text", _boom)

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"not really a pdf", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="pdf_file"' in body  # back on the upload form
    # Apostrophe in "couldn't" is HTML-escaped, so match an apostrophe-free span.
    assert "process that document" in body.lower()


def test_screen7_accept_scaffolds_bundle_and_finishes(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"
    # Bundle now exists in the working copy and reads back as foundational.
    from ingest.policy_reader import BundleAwarePolicyReader
    policies = list(BundleAwarePolicyReader(working_copy).read())
    assert [p.slug for p in policies] == ["document-retention"]
    assert policies[0].foundational is True
    assert (working_copy / "document-retention" / "source.pdf").is_file()


def test_screen7_reupload_clears_draft(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "reupload"})
    assert resp.status_code == 200
    assert 'name="pdf_file"' in resp.content.decode()  # back to upload form
