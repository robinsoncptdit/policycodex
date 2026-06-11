"""Tests for the screen-7 HTMX fragment endpoint (APP-28c).

These exercise `screen7_fragment` (routed at `htmx:onboarding_screen7`), the
in-page fragment counterpart to the full-page `handle()` flow tested in
`test_onboarding_views.py`. They reuse that module's stubbing approach: patch
the module-local `extract_text` / `ClaudeProvider` / `extract_retention_bundle`
/ `GitHubProvider` symbols so no network, Anthropic init, or real git happens,
and point the working copy at a tmp dir via settings (the `working_copy`
fixture). The full-page POSTs in `_advance_to_retention_policy` populate the
shared test-client session so the fragment `accept` path has wizard data.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    # DISC-03: _admin_exists() gates onboarding steps; use create_superuser so
    # tests navigating to retention-policy are not blocked by Signal 1.
    return User.objects.create_superuser(username="admin", password="secret", email="t@e.com")


GITHUB_REPO_CONTINUE = {
    "action": "continue",
    "mode": "connect",
    "repo_url": "https://github.com/acme/policies",
    "branch": "main",
}

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
    working_dir = tmp_path / "policies"
    policies_dir = working_dir / "policies"
    policies_dir.mkdir(parents=True)
    # propose_change needs a real git repo on the default branch (APP-33).
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
    """Replace GitHubProvider with a recorder that does no real git/network work
    and returns a canned PR (mirrors test_onboarding_views.py)."""
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


def _advance_to_retention_policy(client):
    """Walk the full-page wizard to screen 6 (retention-policy) so the shared
    session carries the onboarding data the fragment `accept` path serializes
    into config.yaml. DISC-03: new STEPS order is admin-account -> github-app
    -> llm-provider -> github-repo -> configuration -> retention-policy."""
    for slug in ["admin-account", "github-app", "llm-provider"]:
        client.post(f"/onboarding/{slug}/", {"action": "continue"})
    client.post("/onboarding/github-repo/", GITHUB_REPO_CONTINUE)
    client.post("/onboarding/configuration/", {"action": "continue"})


def _pdf_upload(name="retention.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4", content_type="application/pdf")


# --- 1. extract success -> review fragment -------------------------------

def test_extract_success_returns_review_fragment(client, user, working_copy, stub_extraction):
    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(
        reverse("htmx:onboarding_screen7"),
        {"action": "extract", "pdf_file": _pdf_upload()},
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "screen7-body" in body
    # Review-only markers: the classifications count and a rendered id/name row.
    assert "2 classifications" in body
    assert "1 retention rows" in body
    assert "administrative" in body
    assert "Administrative" in body
    assert 'value="accept"' in body
    assert 'value="reupload"' in body


# --- 2. empty-PDF guard never calls the AI -------------------------------

def test_empty_pdf_guard_returns_upload_fragment_and_never_calls_ai(
    client, user, working_copy, monkeypatch
):
    from app.onboarding import retention_policy as rp

    called = {"ai": False}

    def _boom(*a, **k):
        called["ai"] = True
        raise AssertionError("AI must not be called on an empty PDF")

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: True)
    monkeypatch.setattr(rp, "extract_retention_bundle", _boom)

    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(
        reverse("htmx:onboarding_screen7"),
        {"action": "extract", "pdf_file": _pdf_upload("scan.pdf")},
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "screen7-body" in body
    assert "scanned PDF" in body          # scan-specific guard message
    assert 'name="pdf_file"' in body       # back on the upload form, not review
    assert called["ai"] is False


def test_empty_non_image_pdf_guard_uses_generic_message_and_never_calls_ai(
    client, user, working_copy, monkeypatch
):
    from app.onboarding import retention_policy as rp

    called = {"ai": False}

    def _boom(*a, **k):
        called["ai"] = True
        raise AssertionError("AI must not be called on an empty PDF")

    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_text", lambda path: "   \n  ")
    monkeypatch.setattr(rp, "pdf_has_embedded_images", lambda path: False)
    monkeypatch.setattr(rp, "extract_retention_bundle", _boom)

    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(
        reverse("htmx:onboarding_screen7"),
        {"action": "extract", "pdf_file": _pdf_upload("blank.pdf")},
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "screen7-body" in body
    assert "readable text" in body          # generic, non-scan message
    assert "scanned PDF" not in body
    assert 'name="pdf_file"' in body
    assert called["ai"] is False


# --- 2b. AI provider outage -> reusable ai_outage.html fragment -----------

def test_extraction_outage_renders_reusable_ai_outage_fragment(
    client, user, working_copy, monkeypatch
):
    from app.onboarding import retention_policy as rp

    def _outage(*a, **k):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(rp, "extract_text", lambda path: "FAKE PDF TEXT")
    monkeypatch.setattr(rp, "ClaudeProvider", lambda *a, **k: object())
    monkeypatch.setattr(rp, "extract_retention_bundle", _outage)

    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(
        reverse("htmx:onboarding_screen7"),
        {"action": "extract", "pdf_file": _pdf_upload()},
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    # The shared AI-outage partial is surfaced (spec: reusable outage fragment),
    # the wizard falls back to the upload state, and no draft is staged.
    assert "We couldn't reach the AI service" in body
    assert 'name="pdf_file"' in body
    assert not (working_copy.parent / ".policycodex-staging" / "retention-policy" / "draft.yaml").exists()


# --- 3. accept success -> 204 + HX-Redirect to policy-documents -----------
#
# DISC-09: accept no longer opens a PR. The bundle is staged in the working
# copy; DISC-14's refactored finalize_onboarding opens one bulk PR at the end
# of the inventory pass together with the extracted policy drafts.

@pytest.mark.skip(reason="DISC-14: accept redirects to inventory, not onboarding-complete")
def test_accept_success_returns_204_and_hx_redirect_to_complete(
    client, user, working_copy, stub_extraction, stub_git_provider
):
    """Superseded by test_accept_success_advances_to_policy_documents below."""


def test_accept_success_advances_to_policy_documents(
    client, user, working_copy, stub_extraction, monkeypatch
):
    """DISC-09: accept scaffolds the bundle and redirects to policy-documents
    (no PR opened; that is deferred to DISC-14)."""
    from app.onboarding import retention_policy as rp
    from django.urls import reverse as dj_reverse

    # finalize_onboarding was removed from this module in DISC-09; verify it
    # cannot be called by asserting it is not an attribute.
    assert not hasattr(rp, "finalize_onboarding"), (
        "finalize_onboarding must not be imported in retention_policy after DISC-09"
    )
    monkeypatch.setattr(rp, "scaffold_retention_bundle",
                        lambda *a, **kw: working_copy / "document-retention")
    client.force_login(user)
    _advance_to_retention_policy(client)
    # Stage a draft so accept has something to scaffold.
    wc_dir = working_copy.parent
    staging = wc_dir / ".policycodex-staging" / "retention-policy"
    staging.mkdir(parents=True, exist_ok=True)
    import yaml
    (staging / "draft.yaml").write_text(
        yaml.safe_dump({
            "title": "Document Retention Policy",
            "owner": "CFO",
            "classifications": [],
            "retention_schedule": [],
            "data_yaml": "foo: bar\n",
        }), encoding="utf-8")
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "accept"})
    assert resp.status_code == 204
    assert "HX-Redirect" in resp
    assert resp["HX-Redirect"] == dj_reverse("onboarding_step", kwargs={"step": "policy-documents"})


# --- 4. back and save_exit -> 204 + HX-Redirect --------------------------

def test_back_returns_204_with_hx_redirect_to_previous_step(client, user, working_copy):
    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "back"})
    assert resp.status_code == 204
    assert "HX-Redirect" in resp
    # Previous step before retention-policy is configuration (DISC-03 STEPS order).
    assert resp["HX-Redirect"] == reverse("onboarding_step", kwargs={"step": "configuration"})


def test_save_exit_returns_204_with_hx_redirect_to_catalog(client, user, working_copy):
    client.force_login(user)
    _advance_to_retention_policy(client)
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "save_exit"})
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == reverse("catalog")


# --- 5. CSRF enforcement -------------------------------------------------

def test_post_without_csrf_token_is_forbidden(user, working_copy, db):
    """The default test client exempts CSRF; with enforcement on, a tokenless
    POST is rejected (403). Use the cheap `back` path."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    resp = csrf_client.post(reverse("htmx:onboarding_screen7"), {"action": "back"})
    assert resp.status_code == 403


# --- 6. accept with no staged draft -> upload fragment, not 500 ----------

def test_accept_with_no_staged_draft_returns_upload_fragment(client, user, working_copy):
    client.force_login(user)
    _advance_to_retention_policy(client)
    # No extract ran, so no draft.yaml is staged.
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "accept"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "screen7-body" in body
    assert 'name="pdf_file"' in body   # upload form, not a 500


# --- 7. finalize failure -> deferred to DISC-14 ---------------------------
#
# DISC-09: _do_accept no longer calls finalize_onboarding, so there is no
# "finalize failure" path here. The bulk PR + error handling moves to DISC-14.

@pytest.mark.skip(reason="DISC-14: finalize_onboarding moved out of _do_accept")
def test_finalize_failure_rerenders_review_with_error_message(
    client, user, working_copy, stub_extraction, monkeypatch
):
    pass


# --- 8. method + auth guards ---------------------------------------------

def test_get_returns_405(client, user, working_copy):
    client.force_login(user)
    resp = client.get(reverse("htmx:onboarding_screen7"))
    assert resp.status_code == 405


def test_unauthenticated_post_redirects_to_login(client, working_copy, db):
    resp = client.post(reverse("htmx:onboarding_screen7"), {"action": "back"})
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
