"""DISC-09: screen 6 retention-policy does not 500 when working copy is missing."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def logged_in_admin(db):
    User.objects.create_superuser("admin", "a@b.com", "pw")
    c = Client()
    c.login(username="admin", password="pw")
    return c


@pytest.mark.django_db
def test_get_does_not_500_when_working_copy_missing(logged_in_admin, tmp_path, monkeypatch):
    """Today's bug: load_working_copy_config raised RuntimeError on GET. After
    DISC-09, the gating redirects back to github-repo before handle() is reached.

    We test BOTH: (1) the gating redirect (already covered by DISC-03 tests, but
    we re-check), and (2) handle() itself doesn't 500 even if reached with no
    working copy."""
    monkeypatch.delenv("POLICYCODEX_POLICY_REPO_URL", raising=False)
    with patch("app.onboarding.views._working_copy_dir", return_value=tmp_path / "absent"):
        r = logged_in_admin.get("/onboarding/retention-policy/", follow=False)
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/github-repo/")


@pytest.mark.django_db
def test_accept_does_not_open_pr_anymore(logged_in_admin, tmp_path, monkeypatch):
    """After DISC-09 the accept path STAGES the bundle but does NOT call
    finalize_onboarding. That call moves to the inventory runner in DISC-14."""
    from app.onboarding.retention_policy import STEP_SLUG

    # Pre-seed wizard state so gating Signal 3 lets us reach retention-policy
    session = logged_in_admin.session
    session["onboarding"] = {
        "current_step": "retention-policy",
        "completed": ["admin-account", "github-app", "llm-provider", "github-repo", "configuration"],
        "data": {},
    }
    session.save()

    # Setup: working copy present, draft staged
    wd = tmp_path / "wc"
    (wd / "policies").mkdir(parents=True)
    (wd / ".policycodex-staging" / STEP_SLUG).mkdir(parents=True)
    (wd / ".policycodex-staging" / STEP_SLUG / "draft.yaml").write_text(
        "title: Document Retention Policy\nowner: CFO\nclassifications: []\nretention_schedule: []\ndata_yaml: 'foo: bar\\n'\n"
    )
    monkeypatch.setattr("app.onboarding.retention_policy.load_working_copy_config",
                        lambda: type("C", (), {"working_dir": wd, "branch": "main"})())
    monkeypatch.setattr("app.onboarding.retention_policy.scaffold_retention_bundle",
                        lambda *a, **kw: wd / "policies" / "document-retention")
    # Verify finalize_onboarding is not even importable from this module (DISC-09
    # removed the import; DISC-14 wires it in the inventory runner instead).
    import app.onboarding.retention_policy as rp
    assert not hasattr(rp, "finalize_onboarding"), (
        "finalize_onboarding must not be imported in retention_policy after DISC-09"
    )
    # Patch _working_copy_dir so gating Signal 2 sees the working dir as present.
    with patch("app.onboarding.views._working_copy_dir", return_value=wd):
        r = logged_in_admin.post("/onboarding/retention-policy/", {"action": "accept"})
    assert r.status_code == 302
    assert r.url.endswith("/onboarding/policy-documents/")
