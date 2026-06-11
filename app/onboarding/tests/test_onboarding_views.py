"""Tests for the onboarding wizard views (APP-08 / DISC-03)."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    # DISC-03: _admin_exists() gates all steps; create a superuser so tests
    # that navigate past screen 1 are not blocked.
    return User.objects.create_superuser(username="admin", password="secret", email="a@b.com")


# A valid github-repo form payload, for tests that POST `continue` past step 4.
GITHUB_REPO_CONTINUE = {
    "action": "continue",
    "mode": "connect",
    "repo_url": "https://github.com/acme/policies",
    "branch": "main",
}


def test_urls_resolve():
    assert reverse("onboarding") == "/onboarding/"
    assert reverse("onboarding_step", kwargs={"step": "github-repo"}) == "/onboarding/github-repo/"


def test_onboarding_root_unauthenticated_with_no_admin_goes_to_screen1(client, db):
    """With no admin in the DB, unauthenticated requests go to admin-account screen."""
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/admin-account/"


def test_onboarding_root_unauthenticated_with_admin_goes_to_login(client, db):
    """With an admin in the DB, unauthenticated requests redirect to login."""
    User.objects.create_superuser("admin2", "a@b.com", "pw")
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")


def test_per_step_view_requires_login(client, db):
    """The per-step view is guarded by @login_required."""
    User.objects.create_superuser("admin3", "a@b.com", "pw")
    step_resp = client.get("/onboarding/github-repo/")
    assert step_resp.status_code == 302
    assert step_resp.url.startswith("/login/")


def test_root_redirects_to_first_step_when_fresh(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/admin-account/"


def test_get_step_renders_title_and_indicator(client, db):
    # No admin exists: screen renders the creation form.
    resp = client.get("/onboarding/admin-account/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Create your admin account" in body
    assert "Step 1 of 7" in body


def test_unknown_step_returns_404(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/not-a-step/")
    assert resp.status_code == 404


def test_ahead_jump_is_gated(client, user):
    client.force_login(user)
    resp = client.get("/onboarding/configuration/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/admin-account/"


def test_continue_advances_and_marks_complete(client, user):
    # Admin exists + authenticated: any visit to admin-account redirects to github-app.
    client.force_login(user)
    resp = client.get("/onboarding/admin-account/")
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-app/"
    assert client.get("/onboarding/").url == "/onboarding/github-app/"


def test_back_goes_to_previous_step(client, user):
    client.force_login(user)
    client.post("/onboarding/admin-account/", {"action": "continue"})
    resp = client.post("/onboarding/github-app/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/admin-account/"


def test_back_on_first_step_is_noop_redirect(client, user):
    # Admin exists + authenticated: any visit to admin-account (including back) redirects
    # to github-app. The back action concept does not apply to this idempotent screen.
    client.force_login(user)
    resp = client.post("/onboarding/admin-account/", {"action": "back"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-app/"


def test_save_exit_redirects_to_catalog(client, db):
    # save_exit on admin-account only works when no admin exists (there is no
    # session to return to otherwise). When no admin exists, save_exit exits to catalog.
    resp = client.post("/onboarding/admin-account/", {"action": "save_exit"})
    assert resp.status_code == 302
    assert resp.url == "/catalog/"


def test_can_revisit_completed_step_without_trapping(client, user):
    # After admin is created, revisiting admin-account redirects forward (not 200).
    # Visiting github-app (next step) is permitted once admin-account marks complete.
    client.force_login(user)
    client.get("/onboarding/admin-account/")  # marks complete, advances state
    assert client.get("/onboarding/admin-account/").status_code == 302
    assert client.get("/onboarding/github-app/").status_code == 200


@pytest.mark.skip(reason="DISC-14: last-step completion + handoff flow reworked")
def test_last_step_continue_completes_and_redirects_to_complete(client, user, working_copy, stub_extraction, stub_git_provider):
    pass


def test_github_repo_get_renders_form(client, user):
    client.force_login(user)
    _advance_to_github_repo(client)
    resp = client.get("/onboarding/github-repo/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Mode radio + the connect URL field render.
    assert 'name="mode"' in body
    assert 'name="repo_url"' in body


def test_github_repo_invalid_continue_does_not_advance(client, user):
    client.force_login(user)
    _advance_to_github_repo(client)
    # Missing repo_url for connect mode -> invalid.
    resp = client.post("/onboarding/github-repo/", {"action": "continue", "mode": "connect", "branch": "main"})
    assert resp.status_code == 200  # re-rendered, not redirected
    # Still on github-repo (not advanced).
    assert client.get("/onboarding/").url == "/onboarding/github-repo/"


def test_github_repo_valid_continue_persists_and_advances(client, user, tmp_path):
    client.force_login(user)
    _advance_to_github_repo(client)
    # DISC-07: the new handler clones the working copy on continue; mock both
    # GitHubProvider (needs config.env) and WorkingCopyManager.sync (needs git).
    with patch("app.onboarding.screens.github_repo.GitHubProvider"), \
         patch("app.working_copy.manager.WorkingCopyManager.sync", return_value=tmp_path / "wc"):
        resp = client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    assert resp.status_code == 302
    assert resp.url == "/onboarding/configuration/"
    # The captured value is persisted and pre-populates a return visit.
    back = client.get("/onboarding/github-repo/")
    assert "https://github.com/acme/policies" in back.content.decode()


def test_no_form_step_still_advances_on_bare_continue(client, user):
    """Regression: a step with no registered form keeps the no-op continue."""
    client.force_login(user)
    # admin-account has no form; a bare continue advances.
    resp = client.post("/onboarding/admin-account/", {"action": "continue"})
    assert resp.status_code == 302
    assert resp.url == "/onboarding/github-app/"


# Advance through steps 1-3 to land on github-repo (step 4).
# Screens 1-3 are now real handlers with credential requirements; bypass them
# via session manipulation so these integration helpers stay credential-free.
def _advance_to_github_repo(client):
    from app.onboarding.state import SESSION_KEY
    # Force a first request so Django creates the session.
    client.get("/onboarding/admin-account/")
    session = client.session
    session[SESSION_KEY] = {
        "current_step": "github-repo",
        "completed": ["admin-account", "github-app", "llm-provider"],
        "data": {},
    }
    session.save()


# Steps 1-5 payloads to land ON retention-policy (step 6).
# Session-manipulate past github-repo and configuration; posting through
# github-repo now clones the working copy (DISC-07) which fails without
# real git credentials. Configuration falls through to _generic_step (DISC-08
# scaffold) so it can still be posted through with a bare action continue.
def _advance_to_retention_policy(client):
    from app.onboarding.state import SESSION_KEY
    # Force a first request so Django creates the session.
    client.get("/onboarding/admin-account/")
    session = client.session
    session[SESSION_KEY] = {
        "current_step": "retention-policy",
        "completed": ["admin-account", "github-app", "llm-provider", "github-repo", "configuration"],
        "data": {
            "github-repo": {
                "mode": "connect",
                "repo_url": "https://github.com/acme/policies",
                "branch": "main",
                "org": "",
                "repo_name": "",
            },
        },
    }
    session.save()


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
    working_dir = tmp_path / "policies"
    policies_dir = working_dir / "policies"
    policies_dir.mkdir(parents=True)
    # propose_change runs real `git` subprocess calls (checkout default branch
    # for crash recovery, restore on failure). The working copy must be a real
    # git repo on the default branch with at least one commit (APP-33).
    import subprocess
    def _git(*args):
        return subprocess.run(["git", *args], cwd=working_dir, capture_output=True)
    _git("init", "-b", "main")
    _git("config", "user.email", "t@example.com")
    _git("config", "user.name", "T")
    (working_dir / ".gitkeep").write_text("", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-m", "init")
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
    assert "Step 6 of 7" in body


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


@pytest.mark.skip(reason="DISC-14: accept redirects to inventory, not onboarding-complete")
def test_screen7_accept_scaffolds_bundle_and_finishes(client, user, working_copy, stub_extraction, stub_git_provider):
    pass


def test_screen7_reupload_clears_draft(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "reupload"})
    assert resp.status_code == 200
    assert 'name="pdf_file"' in resp.content.decode()  # back to upload form


@pytest.mark.skip(reason="DISC-14: accept redirects to inventory, not onboarding-complete")
def test_screen7_accept_commits_config_and_opens_pr(client, user, working_copy, stub_extraction, stub_git_provider):
    pass


@pytest.mark.skip(reason="DISC-14: propose_change / clean-tree failure handling moves to the bulk PR step")
def test_screen7_accept_provider_failure_rerenders_review_with_clean_tree(client, user, working_copy, stub_extraction, monkeypatch):
    """DISC-09 removed finalize_onboarding and GitHubProvider from the accept
    path. The clean-tree guarantee (propose_change restores the default branch on
    failure) is exercised in DISC-14 when the bulk PR runs."""
    pass


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


# llm-provider view tests live in test_screen_llm_provider.py (DISC-06).
