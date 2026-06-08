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


def test_last_step_continue_completes_and_redirects_to_catalog(client, user, working_copy, stub_extraction, stub_git_provider):
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


# Steps 1-5 payloads to land ON llm-provider (step 6). Only github-repo has a
# real form before step 6.
def _advance_to_llm_provider(client):
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    for slug in ["address-scheme", "versioning", "reviewer-roles", "retention"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})


# Steps 1-6 payloads to reach screen 7. llm-provider now requires a provider.
def _advance_to_retention_policy(client):
    _advance_to_llm_provider(client)
    client.post("/onboarding/llm-provider/", {"action": "continue", "provider": "claude"})


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


@pytest.fixture
def stub_git_provider(monkeypatch):
    """Replace GitHubProvider in the screen-7 handler with a recorder that does
    no real git/network work and returns a canned PR."""
    from app.onboarding import retention_policy as rp

    class _RecorderProvider:
        instances = []

        def __init__(self):
            self.calls = []
            _RecorderProvider.instances.append(self)

        def branch(self, name, working_dir):
            self.calls.append(("branch", name))

        def commit(self, *, message, files, author_name, author_email, working_dir):
            self.calls.append(("commit", list(files)))
            return "deadbeef"

        def push(self, branch, working_dir):
            self.calls.append(("push", branch))

        def open_pr(self, *, title, body, head_branch, base_branch, working_dir):
            self.calls.append(("open_pr", head_branch))
            return {
                "pr_number": 1,
                "url": "https://github.com/acme/policies/pull/1",
                "state": "drafted",
            }

    monkeypatch.setattr(rp, "GitHubProvider", _RecorderProvider)
    return _RecorderProvider


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


def test_screen7_accept_scaffolds_bundle_and_finishes(client, user, working_copy, stub_extraction, stub_git_provider):
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


def test_screen7_accept_commits_config_and_opens_pr(client, user, working_copy, stub_extraction, stub_git_provider):
    import yaml

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})

    assert resp.status_code == 302
    assert resp.url == "/catalog/"

    working_dir = working_copy.parent
    config_path = working_dir / ".policycodex" / "config.yaml"
    assert config_path.is_file()
    doc = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert doc["onboarding"]["github-repo"]["repo_url"] == "https://github.com/acme/policies"

    provider = stub_git_provider.instances[-1]
    assert [c[0] for c in provider.calls] == ["branch", "commit", "push", "open_pr"]
    commit_files = [c for c in provider.calls if c[0] == "commit"][0][1]
    assert config_path in commit_files
    assert all(".policycodex-staging" not in str(f) for f in commit_files)

    assert not (working_dir / ".policycodex-staging").exists()


def test_screen7_accept_provider_failure_rerenders_review_and_keeps_local(client, user, working_copy, stub_extraction, monkeypatch):
    from app.onboarding import retention_policy as rp

    class _BoomProvider:
        def branch(self, name, working_dir):
            raise RuntimeError("push rejected by branch protection")

    monkeypatch.setattr(rp, "GitHubProvider", _BoomProvider)

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})

    assert resp.status_code == 200
    assert "Administrative" in resp.content.decode()
    assert (working_copy / "document-retention" / "data.yaml").is_file()


def test_screen7_extract_blocks_scanned_image_only_pdf(client, user, working_copy, monkeypatch):
    """A scanned/image-only PDF extracts to empty text. The wizard must warn and
    stay on the upload form, and must NOT call the AI (which would otherwise
    produce empty classifications and let onboarding proceed)."""
    from app.onboarding import retention_policy as rp

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: True)
    ai_calls = []
    monkeypatch.setattr(
        rp, "extract_retention_bundle",
        lambda provider, text: ai_calls.append(text) or FAKE_BUNDLE,
    )

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("scan.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="pdf_file"' in body          # back on the upload form, not review
    assert "scanned pdf" in body.lower()       # scan-specific guidance
    assert ai_calls == []                       # the AI extraction was never called


def test_screen7_extract_blocks_empty_text_pdf(client, user, working_copy, monkeypatch):
    """An empty/blank PDF that is not image-only also blocks, with a generic
    'no readable text' message rather than the scan-specific one."""
    from app.onboarding import retention_policy as rp

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "   \n  ")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: False)
    ai_calls = []
    monkeypatch.setattr(
        rp, "extract_retention_bundle",
        lambda provider, text: ai_calls.append(text) or FAKE_BUNDLE,
    )

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("blank.pdf", b"%PDF-1.4", content_type="application/pdf")
    resp = client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="pdf_file"' in body
    assert "readable text" in body.lower()
    assert ai_calls == []


def test_llm_provider_get_renders_picker(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.get("/onboarding/llm-provider/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Step 6 of 7" in body
    assert 'name="provider"' in body


def test_llm_provider_valid_continue_persists_and_advances(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.post(
        "/onboarding/llm-provider/", {"action": "continue", "provider": "openai"}
    )
    assert resp.status_code == 302
    assert resp.url == "/onboarding/retention-policy/"
    # The choice persists: a return visit restores the selection (one radio checked).
    back = client.get("/onboarding/llm-provider/")
    back_body = back.content.decode()
    assert 'value="openai"' in back_body
    assert "checked" in back_body


def test_llm_provider_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    resp = client.post("/onboarding/llm-provider/", {"action": "continue"})
    assert resp.status_code == 200  # re-rendered, not redirected
    assert client.get("/onboarding/").url == "/onboarding/llm-provider/"


def test_llm_provider_screen_shows_api_key_prose(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    body = client.get("/onboarding/llm-provider/").content.decode()
    # The core consumer-subscription distinction is spelled out.
    assert "not Claude Pro" in body
    assert "ChatGPT Plus" in body
    # Each provider's API-key documentation link is present.
    assert "https://docs.anthropic.com/en/api/overview" in body
    assert "https://platform.openai.com/docs/api-reference/authentication" in body
    assert "https://ai.google.dev/gemini-api/docs/api-key" in body
    assert "https://learn.microsoft.com/azure/ai-services/openai/" in body


def test_llm_provider_screen_shows_cost_table_with_caveat(client, user):
    client.force_login(user)
    _advance_to_llm_provider(client)
    body = client.get("/onboarding/llm-provider/").content.decode()
    assert "Illustrative example" in body          # placeholder caveat
    assert "mid-tier model" in body                 # assumption note
    assert "Mid (~200 policies)" in body            # a table row renders
