# APP-18 Approve Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A POST endpoint and UI button that approve an open PR by calling GitHub's review API via a new `GitProvider.approve_pr` method, gate-guarded so only `drafted`-state PRs can be approved.

**Architecture:** New abstract method `approve_pr(pr_number, working_dir, body) -> dict` on `GitProvider`; `GitHubProvider` implements it by calling `repo.get_pull(pr_number).create_review(body=body, event="APPROVE")` and returning a small metadata dict. A new function-based Django view at `POST /policies/approve/` (form-encoded `pr_number`) reads `read_pr_state` first; only `"drafted"` proceeds, anything else returns a flash error and redirects to `/catalog/`. The catalog template gains a small "Approve PR" form that takes a PR number; APP-07 and APP-17 will later wire per-policy PR numbers onto each catalog row. The "reviewer" attribution comes from the GitHub App token's identity (per ticket text); the Django user is logged in the server-side audit log via `logger.info`.

**Tech Stack:** Django 5+ function-based views, PyGithub (`Repository.get_pull(...).create_review(event="APPROVE")`), pytest-django, `unittest.mock`.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-18 line 100. Depends on APP-04 (the GitHub provider, merged Week 2). The PR-state-to-gate mapping (APP-17) and edit-form (APP-07) are sibling Wave-3 tickets; this plan deliberately does NOT couple to them, so a PR number is supplied directly via form input for v0.1. APP-07 / APP-17 wire the per-row "Approve" button to the right PR number in their own tickets.

**BASE:** `main` at SHA `5017488`.

**Discipline reminders:**

- TDD strict: every test must be observed-failing first, then passing. Don't skip RED.
- No em dashes anywhere in new content (code, docstrings, comments, commit messages).
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens anywhere in `app/git_provider/`, `core/views.py`, the template, or test fixtures. Test fixtures use synthetic slugs (`onboarding`, `code-of-conduct`, `retention`).
- `>=` floor pins in any requirements file (none needed here — PyGithub already pinned via APP-04).

---

## File Structure

- Modify: `app/git_provider/base.py` — add abstract `approve_pr(pr_number, working_dir, body) -> dict` (one more abstract method alongside `open_pr` and `read_pr_state`).
- Modify: `app/git_provider/github_provider.py` — implement `approve_pr` using the same origin-parse → `get_repo` → `get_pull` → `create_review(event="APPROVE")` pattern as `open_pr` / `read_pr_state`.
- Modify: `app/git_provider/tests/test_base.py` — add `test_subclass_missing_approve_pr_fails` AND add a stub `approve_pr` to every existing `IncompleteProvider` subclass so they remain instantiable-failing for their specific missing method (without `approve_pr` being the dominant ABC failure).
- Modify: `app/git_provider/tests/test_github_provider.py` — add `test_approve_pr_*` tests mirroring the `test_open_pr_*` patterns.
- Modify: `core/views.py` — add `approve_pr(request)` function (POST-only, `@login_required`). Reads `pr_number` from `request.POST`; calls `provider.read_pr_state` first; rejects non-drafted with `messages.error` + redirect; on success calls `provider.approve_pr` and adds `messages.success`.
- Modify: `core/urls.py` — add `path("policies/approve/", views.approve_pr, name="approve_pr")`.
- Modify: `core/templates/catalog.html` — add a small "Approve PR" form scoped under `{% if not is_empty_onboarding %}` with a numeric `pr_number` input, CSRF token, and submit button. (Per-row wiring lands in APP-17.)
- Create: `core/tests/test_approve_pr.py` — pytest tests for the view (login required, POST-only, gate guard, success path, provider error pass-through, audit log line).
- Modify: `policycodex_site/settings.py` — confirm `MESSAGE_STORAGE` is wired (Django default is the session storage; just verify, do not change). No edit unless missing.

No other files touched. The catalog view (`core/views.py::catalog`), the working-copy config, and the policy reader are read-only for this ticket.

---

## Task 1: Worktree pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm worktree state**

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

Expected: BASE SHA `5017488` or a descendant; branch is the auto-worktree branch the harness gave you (something like `worktree-agent-<id>`); status clean.

If anything is unexpected, STOP and report.

- [ ] **Step 2: Merge `main` into your worktree branch**

```bash
git fetch
git merge main --no-edit
```

Expected: "Already up to date." or a clean fast-forward.

- [ ] **Step 3: Confirm baseline test suite is green**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `180 passed`. Capture the number.

- [ ] **Step 4: Read the existing patterns this ticket follows**

Read these files briefly to confirm signatures:

- `/Users/chuck/PolicyWonk/app/git_provider/base.py` (the ABC + existing `@abstractmethod` style)
- `/Users/chuck/PolicyWonk/app/git_provider/github_provider.py:208-256` (`open_pr` and `read_pr_state` — the closest analogs to `approve_pr`)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_github_provider.py:188-249` (PyGithub mock pattern for `create_pull` and `get_pull` + `get_reviews`)
- `/Users/chuck/PolicyWonk/app/git_provider/tests/test_base.py:16-150` (the `IncompleteProvider` subclass pattern for each missing-method test)
- `/Users/chuck/PolicyWonk/core/views.py` (function-based view + `@login_required` style)
- `/Users/chuck/PolicyWonk/core/urls.py` (URL routing style; already has `catalog`, `root_redirect`, `health`)
- `/Users/chuck/PolicyWonk/core/templates/catalog.html` (where the approve form will go)
- `/Users/chuck/PolicyWonk/core/tests/test_auth.py:8-17` (user fixture + `force_login` pattern)
- `/Users/chuck/PolicyWonk/core/tests/test_catalog.py:1-25` (POST/redirect assertions; `@login_required` redirect chain)

- [ ] **Step 5: Confirm Django's MESSAGES framework is wired**

```bash
grep -n "django.contrib.messages\|MESSAGE_STORAGE" /Users/chuck/PolicyWonk/policycodex_site/settings.py
```

Expected: `'django.contrib.messages'` appears in `INSTALLED_APPS` and `'django.contrib.messages.middleware.MessageMiddleware'` in `MIDDLEWARE`. (Both are part of the Django startproject default; APP-21 added the working_copy app alongside.) If either is missing, STOP and report — the success/error flash relies on this.

- [ ] **Step 6: No commit yet.**

---

## Task 2: Add `approve_pr` to the `GitProvider` ABC (TDD)

**Files:**
- Modify: `app/git_provider/base.py`
- Modify: `app/git_provider/tests/test_base.py`

- [ ] **Step 1: Write the failing test**

Open `app/git_provider/tests/test_base.py`. Append to the `TestGitProviderSubclassMissingMethods` class:

```python
    def test_subclass_missing_approve_pr_fails(self):
        """Subclass missing approve_pr() cannot instantiate."""
        class IncompleteProvider(GitProvider):
            def clone(self, repo_url: str, dest: Path) -> None:
                pass
            def branch(self, name: str, working_dir: Path) -> None:
                pass
            def commit(self, message: str, files: list[Path], author_name: str, author_email: str, working_dir: Path) -> str:
                pass
            def push(self, branch: str, working_dir: Path) -> None:
                pass
            def pull(self, branch: str, working_dir: Path) -> None:
                pass
            def open_pr(self, title: str, body: str, head_branch: str, base_branch: str, working_dir: Path) -> dict:
                pass
            def read_pr_state(self, pr_number: int, working_dir: Path) -> str:
                pass

        with pytest.raises(TypeError):
            IncompleteProvider()
```

- [ ] **Step 2: Run to confirm the new test FAILS for the right reason**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py::TestGitProviderSubclassMissingMethods::test_subclass_missing_approve_pr_fails -v 2>&1 | tail -10
```

Expected: the test FAILS because the `IncompleteProvider` class above DOES instantiate (since `approve_pr` is not yet abstract on `GitProvider`). The test expects `TypeError` but gets none, so it fails. This is the correct RED state.

Confirm by also running:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: the 7 existing tests PASS plus the new one FAILS (8 collected, 7 passed, 1 failed). Capture the failure message for later confirmation that it flips to PASS.

- [ ] **Step 3: Add `approve_pr` to the ABC**

Open `app/git_provider/base.py`. Append to the class body (after `read_pr_state`):

```python
    @abstractmethod
    def approve_pr(self, pr_number: int, working_dir: Path, body: str = "") -> dict:
        """Approve a pull request on behalf of the authenticated reviewer.

        The "reviewer" identity is the credential the implementation uses
        to call the provider's review API (e.g., the GitHub App installation
        token for GitHubProvider). The application-layer audit log captures
        the Django user who initiated the action.

        Args:
            pr_number: The pull request number.
            working_dir: Path to the repository working directory.
            body: Optional review body text. Defaults to empty string,
                which provider implementations may map to "no comment".

        Returns:
            Dictionary containing review metadata (at minimum:
            review_id, state, pr_number).
        """
        pass
```

- [ ] **Step 4: Add stub `approve_pr` to every OTHER `IncompleteProvider` in `test_base.py`**

Each existing `test_subclass_missing_<method>_fails` test builds an `IncompleteProvider` that implements all abstract methods EXCEPT one. With `approve_pr` now abstract, every one of those subclasses also needs a stub `approve_pr` method so they remain instantiable-failing only for THEIR specific missing method (not for `approve_pr`).

For each of the following 7 tests (lines 19, 38, 57, 76, 95, 114, 133), add this method to its `IncompleteProvider` body, immediately after the last existing `def` and before the `with pytest.raises(TypeError):`:

```python
            def approve_pr(self, pr_number: int, working_dir: Path, body: str = "") -> dict:
                pass
```

The 7 tests to patch:
1. `test_subclass_missing_clone_fails`
2. `test_subclass_missing_branch_fails`
3. `test_subclass_missing_commit_fails`
4. `test_subclass_missing_push_fails`
5. `test_subclass_missing_pull_fails`
6. `test_subclass_missing_open_pr_fails`
7. `test_subclass_missing_read_pr_state_fails`

Each one keeps its existing `pytest.raises(TypeError)` expectation; the only addition is the stub `approve_pr` method on the subclass.

- [ ] **Step 5: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_base.py -v 2>&1 | tail -15
```

Expected: 8 passing (the 7 existing + 1 new).

- [ ] **Step 6: Confirm `GitHubProvider` instantiation NOW fails at the next test layer**

`GitHubProvider` does not yet implement `approve_pr`, so instantiating it (which several `test_github_provider.py` tests do) should now fail. Verify:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -v 2>&1 | tail -15
```

Expected: many tests fail with `TypeError: Can't instantiate abstract class GitHubProvider with abstract method approve_pr`. This is correct RED for Task 3.

- [ ] **Step 7: Commit**

```bash
git add app/git_provider/base.py app/git_provider/tests/test_base.py
git commit -m "feat(APP-18): add approve_pr to GitProvider ABC + base-class tests"
```

---

## Task 3: Implement `GitHubProvider.approve_pr` (TDD)

**Files:**
- Modify: `app/git_provider/github_provider.py`
- Modify: `app/git_provider/tests/test_github_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/git_provider/tests/test_github_provider.py`:

```python
def test_approve_pr_creates_review_with_approve_event(tmp_path):
    """approve_pr calls Repository.get_pull(N).create_review(event='APPROVE')."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    wd = tmp_path / "wd"
    fake_review = MagicMock(id=987, state="APPROVED")
    fake_pr = MagicMock(number=42)
    fake_pr.create_review.return_value = fake_review
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        result = p.approve_pr(pr_number=42, working_dir=wd, body="Looks good.")
    fake_client.get_repo.assert_called_once_with("foo/bar")
    fake_repo.get_pull.assert_called_once_with(42)
    fake_pr.create_review.assert_called_once_with(body="Looks good.", event="APPROVE")
    assert result == {"review_id": 987, "state": "APPROVED", "pr_number": 42}


def test_approve_pr_defaults_body_to_empty_string(tmp_path):
    """When no body is supplied, approve_pr passes body='' to create_review."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    fake_review = MagicMock(id=1, state="APPROVED")
    fake_pr = MagicMock(number=7)
    fake_pr.create_review.return_value = fake_review
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        p.approve_pr(pr_number=7, working_dir=tmp_path / "wd")
    fake_pr.create_review.assert_called_once_with(body="", event="APPROVE")


def test_approve_pr_raises_on_origin_lookup_failure(tmp_path):
    """If `git remote get-url origin` fails, approve_pr raises RuntimeError."""
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=128, stderr=b"not a git repo")
        p = GitHubProvider(config=cfg, github_client=MagicMock())
        with pytest.raises(RuntimeError, match="git remote get-url"):
            p.approve_pr(pr_number=1, working_dir=tmp_path / "wd")


def test_approve_pr_propagates_pygithub_exceptions(tmp_path):
    """If PyGithub raises (e.g., GithubException from create_review), bubble it up."""
    from github import GithubException
    cfg = _fake_config(tmp_path)
    (tmp_path / "key.pem").write_text("FAKE PEM")
    fake_pr = MagicMock()
    fake_pr.create_review.side_effect = GithubException(
        status=403, data={"message": "Resource not accessible by integration"}, headers={}
    )
    fake_repo = MagicMock()
    fake_repo.get_pull.return_value = fake_pr
    fake_client = MagicMock()
    fake_client.get_repo.return_value = fake_repo
    with patch("app.git_provider.github_provider.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"https://github.com/foo/bar.git\n")
        p = GitHubProvider(config=cfg, github_client=fake_client)
        with pytest.raises(GithubException):
            p.approve_pr(pr_number=1, working_dir=tmp_path / "wd")
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -v -k approve_pr 2>&1 | tail -10
```

Expected: 4 failures with `TypeError: Can't instantiate abstract class GitHubProvider with abstract method approve_pr` (or `AttributeError` once instantiation works but the method is missing).

- [ ] **Step 3: Implement `approve_pr` in `GitHubProvider`**

Open `app/git_provider/github_provider.py`. Append to the `GitHubProvider` class, after the existing `read_pr_state` method (i.e., at the end of the class body):

```python
    def approve_pr(
        self,
        pr_number: int,
        working_dir: Path,
        body: str = "",
    ) -> dict:
        get_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
        )
        if get_url.returncode != 0:
            raise RuntimeError(
                f"git remote get-url failed (exit {get_url.returncode}): "
                f"{get_url.stderr.decode(errors='replace')}"
            )
        owner_repo = _parse_owner_repo(get_url.stdout.decode())
        repo = self._client.get_repo(owner_repo)
        pr = repo.get_pull(pr_number)
        review = pr.create_review(body=body, event="APPROVE")
        return {
            "review_id": review.id,
            "state": review.state,
            "pr_number": pr_number,
        }
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/git_provider/tests/test_github_provider.py -v 2>&1 | tail -20
```

Expected: all `test_github_provider.py` tests pass (the prior failures from Task 2 Step 6 flip green, plus the 4 new `approve_pr` tests).

- [ ] **Step 5: Full repo suite still green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `185 passed` (180 baseline + 1 new in test_base.py + 4 new in test_github_provider.py). Capture the number.

- [ ] **Step 6: Commit**

```bash
git add app/git_provider/github_provider.py app/git_provider/tests/test_github_provider.py
git commit -m "feat(APP-18): GitHubProvider.approve_pr via PyGithub create_review"
```

---

## Task 4: Approve view + URL + login_required + POST-only (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/tests/test_approve_pr.py`

- [ ] **Step 1: Write the failing tests (scaffold + auth + method gate)**

Create `core/tests/test_approve_pr.py`:

```python
"""Tests for the APP-18 approve_pr view."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="reviewer", password="secret")


def test_approve_pr_url_resolves():
    assert reverse("approve_pr") == "/policies/approve/"


def test_approve_pr_requires_login(client):
    """An anonymous POST is redirected to the login page."""
    response = client.post("/policies/approve/", {"pr_number": "42"})
    assert response.status_code == 302
    assert response.url.startswith("/login/")
    assert "next=/policies/approve/" in response.url


def test_approve_pr_rejects_get(client, user):
    """GET is not allowed (405); the action mutates state and is POST-only."""
    client.force_login(user)
    response = client.get("/policies/approve/")
    assert response.status_code == 405


def test_approve_pr_rejects_missing_pr_number(client, user):
    """A POST without pr_number redirects with a messages.error flash."""
    client.force_login(user)
    response = client.post("/policies/approve/", {})
    assert response.status_code == 302
    assert response.url == "/catalog/"
    # The flash message is stored on the session-backed messages framework
    # and is delivered on the NEXT request (follow=True surfaces it).
    follow = client.get("/catalog/")
    body = follow.content.decode()
    assert "pr_number" in body.lower() or "missing" in body.lower()


def test_approve_pr_rejects_non_numeric_pr_number(client, user):
    """A non-integer pr_number is rejected with a messages.error flash."""
    client.force_login(user)
    response = client.post("/policies/approve/", {"pr_number": "not-a-number"})
    assert response.status_code == 302
    assert response.url == "/catalog/"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_approve_pr.py -v 2>&1 | tail -10
```

Expected: `NoReverseMatch` for `approve_pr` URL name and 404s for `/policies/approve/`.

- [ ] **Step 3: Add the view stub**

Open `core/views.py`. Add these imports at the top (with the existing imports):

```python
import logging

from django.contrib import messages
from django.views.decorators.http import require_POST
```

Add a module-level logger near the top:

```python
logger = logging.getLogger(__name__)
```

Append the view to the end of the file:

```python
@login_required
@require_POST
def approve_pr(request):
    """Approve an open PR on behalf of the authenticated reviewer.

    The Django user who clicked the button is logged for the app's audit
    trail. The GitHub-side actor on the review is the App installation
    identity, per the v0.1 ticket scope.

    v0.1 permission model: any authenticated Django user may approve.
    Future tickets (reviewer-role gating) will add per-user authorization.
    """
    raw = request.POST.get("pr_number", "").strip()
    if not raw:
        messages.error(request, "Missing pr_number.")
        return redirect("catalog")
    try:
        pr_number = int(raw)
    except ValueError:
        messages.error(request, f"Invalid pr_number: {raw!r}.")
        return redirect("catalog")

    # Gate-guard and provider call land in Task 5.
    messages.error(request, "Approve action not yet wired.")
    return redirect("catalog")
```

- [ ] **Step 4: Wire the URL**

Open `core/urls.py`. Add the route. The file ends up as (preserving existing entries):

```python
"""URL routes for the core app."""
from django.urls import path

from . import views


urlpatterns = [
    path("", views.root_redirect, name="root"),
    path("health/", views.health, name="health"),
    path("catalog/", views.catalog, name="catalog"),
    path("policies/approve/", views.approve_pr, name="approve_pr"),
]
```

- [ ] **Step 5: Run to confirm the scaffold tests pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_approve_pr.py -v 2>&1 | tail -12
```

Expected: 5 passing (URL resolves, login required, GET rejected, missing pr_number, non-numeric pr_number).

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/urls.py core/tests/test_approve_pr.py
git commit -m "feat(APP-18): approve_pr view scaffold (URL, auth, POST-only, input validation)"
```

---

## Task 5: Gate-guard + provider call + flash + audit log (TDD)

**Files:**
- Modify: `core/views.py`
- Modify: `core/tests/test_approve_pr.py`

The view currently returns "not yet wired" for valid pr_numbers. This task adds the real logic: read state, gate-guard on `"drafted"`, call `provider.approve_pr`, flash success, log the actor.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_approve_pr.py`:

```python
def test_approve_pr_happy_path_calls_provider_and_flashes_success(client, user, caplog):
    """Drafted PR + valid pr_number → provider.approve_pr called → success flash."""
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = "drafted"
    fake_provider.approve_pr.return_value = {
        "review_id": 555,
        "state": "APPROVED",
        "pr_number": 42,
    }
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            with caplog.at_level("INFO", logger="core.views"):
                response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.read_pr_state.assert_called_once_with(42, "/tmp/wc")
    fake_provider.approve_pr.assert_called_once_with(
        pr_number=42, working_dir="/tmp/wc", body=""
    )
    # Audit log line includes the Django username + the PR number.
    log_text = " ".join(r.message for r in caplog.records)
    assert "reviewer" in log_text
    assert "42" in log_text
    # Success message is surfaced on the next request.
    follow = client.get("/catalog/")
    assert "approved" in follow.content.decode().lower()


@pytest.mark.parametrize("state", ["reviewed", "published", "closed"])
def test_approve_pr_refuses_non_drafted_state(client, user, state):
    """Already-approved, merged, or closed PRs cannot be approved again."""
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = state
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    fake_provider.approve_pr.assert_not_called()
    follow = client.get("/catalog/")
    body = follow.content.decode().lower()
    assert state in body or "cannot be approved" in body


def test_approve_pr_when_working_copy_unconfigured_flashes_error(client, user):
    """If load_working_copy_config raises, the view flashes an error and redirects."""
    client.force_login(user)
    with patch("core.views.load_working_copy_config", side_effect=RuntimeError("repo url unset")):
        response = client.post("/policies/approve/", {"pr_number": "42"})
    assert response.status_code == 302
    assert response.url == "/catalog/"
    follow = client.get("/catalog/")
    body = follow.content.decode().lower()
    assert "working copy" in body or "not configured" in body


def test_approve_pr_provider_exception_flashes_error(client, user):
    """If provider.approve_pr raises, the view flashes the error and redirects."""
    from github import GithubException
    client.force_login(user)
    fake_provider = MagicMock()
    fake_provider.read_pr_state.return_value = "drafted"
    fake_provider.approve_pr.side_effect = GithubException(
        status=403, data={"message": "Resource not accessible"}, headers={}
    )
    with patch("core.views.GitHubProvider", return_value=fake_provider):
        with patch("core.views.load_working_copy_config") as load_cfg:
            load_cfg.return_value = MagicMock(working_dir="/tmp/wc")
            response = client.post("/policies/approve/", {"pr_number": "42"})

    assert response.status_code == 302
    assert response.url == "/catalog/"
    follow = client.get("/catalog/")
    assert "error" in follow.content.decode().lower() or "could not approve" in follow.content.decode().lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_approve_pr.py -v 2>&1 | tail -15
```

Expected: 4 new failures (happy-path, non-drafted-states parametrized into 3, working-copy-unconfigured, provider-exception). The existing 5 from Task 4 stay green except `test_approve_pr_rejects_non_numeric_pr_number` and `test_approve_pr_rejects_missing_pr_number` may temporarily fail if the implementation tries to instantiate the provider for every request — Task 5 Step 3 keeps the early-return for invalid input, so they stay green.

- [ ] **Step 3: Replace the "not yet wired" stub with the real logic**

Open `core/views.py`. Add to the imports near the top:

```python
from app.git_provider.github_provider import GitHubProvider
```

Replace the `approve_pr` function body so it ends up as:

```python
@login_required
@require_POST
def approve_pr(request):
    """Approve an open PR on behalf of the authenticated reviewer.

    The Django user who clicked the button is logged for the app's audit
    trail. The GitHub-side actor on the review is the App installation
    identity, per the v0.1 ticket scope.

    v0.1 permission model: any authenticated Django user may approve.
    Future tickets (reviewer-role gating) will add per-user authorization.

    Gate-guard: only `drafted`-state PRs are approvable. Approving an
    already-reviewed, merged, or closed PR is refused with a flash error.
    The check is at the view layer (not the provider) because v0.1 is a
    single-server single-process app; concurrent-approval races are not
    a real risk at our scale, and surfacing the state in the flash message
    is more useful to the user than a provider-layer raise.
    """
    raw = request.POST.get("pr_number", "").strip()
    if not raw:
        messages.error(request, "Missing pr_number.")
        return redirect("catalog")
    try:
        pr_number = int(raw)
    except ValueError:
        messages.error(request, f"Invalid pr_number: {raw!r}.")
        return redirect("catalog")

    try:
        config = load_working_copy_config()
    except RuntimeError as exc:
        messages.error(request, f"Working copy not configured: {exc}")
        return redirect("catalog")

    provider = GitHubProvider()
    try:
        state = provider.read_pr_state(pr_number, config.working_dir)
    except Exception as exc:
        messages.error(request, f"Could not read PR #{pr_number} state: {exc}")
        logger.warning(
            "approve_pr: read_pr_state failed user=%s pr=%s err=%s",
            request.user.username, pr_number, exc,
        )
        return redirect("catalog")

    if state != "drafted":
        messages.error(
            request,
            f"PR #{pr_number} cannot be approved (current state: {state}).",
        )
        return redirect("catalog")

    try:
        result = provider.approve_pr(
            pr_number=pr_number,
            working_dir=config.working_dir,
            body="",
        )
    except Exception as exc:
        messages.error(request, f"Could not approve PR #{pr_number}: {exc}")
        logger.warning(
            "approve_pr: provider error user=%s pr=%s err=%s",
            request.user.username, pr_number, exc,
        )
        return redirect("catalog")

    logger.info(
        "approve_pr: success user=%s pr=%s review_id=%s",
        request.user.username, pr_number, result.get("review_id"),
    )
    messages.success(request, f"PR #{pr_number} approved.")
    return redirect("catalog")
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_approve_pr.py -v 2>&1 | tail -20
```

Expected: 11 passing (5 from Task 4 + 6 new: 1 happy-path, 3 parametrized non-drafted-state, 1 working-copy-unconfigured, 1 provider-exception).

- [ ] **Step 5: Full repo suite still green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `196 passed` (185 from Task 3 + 11 new in test_approve_pr.py). Capture the number.

- [ ] **Step 6: Confirm flash messages surface in catalog**

The catalog template does not currently render `{% messages %}`. The flash assertions in Task 5 Step 1 work by checking the response body after a follow-up GET. If they fail because the template does not actually display flashes, the implementer must add a flash-rendering block to `base.html` immediately above `{% block content %}`:

```html
{% if messages %}
  <ul class="messages">
    {% for message in messages %}
      <li class="message message-{{ message.tags }}">{{ message }}</li>
    {% endfor %}
  </ul>
{% endif %}
```

If the Task 5 Step 4 run already passes WITHOUT this edit, the flashes are rendered somewhere else (or Django's test client surfaces them differently) — skip this step. If it fails, add the block and re-run.

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/tests/test_approve_pr.py core/templates/base.html
git commit -m "feat(APP-18): approve_pr view gate-guard + provider call + audit log"
```

(Drop `core/templates/base.html` from the `git add` line if Step 6 was skipped.)

---

## Task 6: UI button on the catalog (TDD)

**Files:**
- Modify: `core/templates/catalog.html`
- Modify: `core/tests/test_catalog.py`

The v0.1 button is intentionally simple: a single form at the top of the catalog (not per-row) with a numeric `pr_number` input. APP-07 (edit-form, opens PR per policy) and APP-17 (PR-state-to-gate) will later wire a per-row button with the PR number embedded.

- [ ] **Step 1: Write the failing test**

Append to `core/tests/test_catalog.py`:

```python
def test_catalog_renders_approve_pr_form(client, user):
    """The catalog has a POST form pointing at /policies/approve/ with pr_number input."""
    client.force_login(user)
    with override_settings(
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("core.views.Path.exists", return_value=True):
            with patch("core.views.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter([])
                response = client.get("/catalog/")

    body = response.content.decode()
    assert 'action="/policies/approve/"' in body
    assert 'method="post"' in body.lower()
    assert 'name="pr_number"' in body
    # CSRF token is rendered.
    assert "csrfmiddlewaretoken" in body


def test_catalog_omits_approve_form_in_empty_onboarding_state(client, user):
    """The approve form does NOT render before the working copy exists."""
    client.force_login(user)
    with override_settings(POLICYCODEX_POLICY_REPO_URL=""):
        response = client.get("/catalog/")
    body = response.content.decode()
    assert "No policies yet" in body
    assert 'action="/policies/approve/"' not in body
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v -k approve 2>&1 | tail -8
```

Expected: 2 failures (the form is not yet in the template).

- [ ] **Step 3: Add the approve form to the catalog template**

Open `core/templates/catalog.html`. Inside the `{% else %}` branch (the non-empty-onboarding branch), immediately after `<h2>Policy catalog</h2>` and BEFORE the `<ul class="policy-list">`, insert:

```html
    <section class="approve-pr">
      <h3>Approve a PR</h3>
      <p>
        Enter the GitHub PR number to approve. (APP-17 will wire this to
        per-policy rows once PR tracking is persisted.)
      </p>
      <form method="post" action="/policies/approve/">
        {% csrf_token %}
        <label for="pr_number">PR number</label>
        <input type="number" name="pr_number" id="pr_number" min="1" required>
        <button type="submit">Approve PR</button>
      </form>
    </section>
```

The full template structure becomes:

```html
{% extends "base.html" %}

{% block title %}Catalog | PolicyCodex{% endblock %}

{% block content %}
  <h2>Policy catalog</h2>

  {% if is_empty_onboarding %}
    <section class="empty-state">
      <p>No policies yet.</p>
      <p>
        Run the onboarding wizard, or sync the diocese's policy repo by running
        <code>python manage.py pull_working_copy</code> on the server.
      </p>
    </section>
  {% else %}
    <section class="approve-pr">
      <h3>Approve a PR</h3>
      <p>
        Enter the GitHub PR number to approve. (APP-17 will wire this to
        per-policy rows once PR tracking is persisted.)
      </p>
      <form method="post" action="/policies/approve/">
        {% csrf_token %}
        <label for="pr_number">PR number</label>
        <input type="number" name="pr_number" id="pr_number" min="1" required>
        <button type="submit">Approve PR</button>
      </form>
    </section>

    <ul class="policy-list">
      {% for policy in policies %}
        <li class="policy">
          <a href="#{{ policy.slug }}">{{ policy.frontmatter.title|default:policy.slug }}</a>
          <span class="kind-badge kind-{{ policy.kind }}">{{ policy.kind }}</span>
          {% if policy.foundational %}
            <span class="foundational-badge">(foundational)</span>
          {% endif %}
        </li>
      {% empty %}
        <li class="no-results">No policies in the working copy.</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endblock %}
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest core/tests/test_catalog.py -v 2>&1 | tail -15
```

Expected: all `test_catalog.py` tests pass (the existing 9 + 2 new = 11).

- [ ] **Step 5: Full repo suite green**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `198 passed` (196 from Task 5 + 2 new). Capture the number.

- [ ] **Step 6: Commit**

```bash
git add core/templates/catalog.html core/tests/test_catalog.py
git commit -m "feat(APP-18): approve-PR form on catalog (UI surface for the approve action)"
```

---

## Task 7: Final verification + smoke + handoff

**Files:**
- None modified.

- [ ] **Step 1: Confirm `manage.py check` still clean**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` (Or, if `POLICYCODEX_POLICY_REPO_URL` is unset, one APP-21 Warning. Either is acceptable; exit code must be 0.)

- [ ] **Step 2: Optional smoke against a live PT PR**

If a real PR exists on the PT policy repo and GitHub App credentials are available:

```bash
cd /Users/chuck/PolicyWonk
export POLICYCODEX_POLICY_REPO_URL="https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app18-smoke
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy

# Need a superuser:
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_user('admin', 'admin@example.com', 'admin')" | /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py shell

/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py runserver &
SERVER_PID=$!
sleep 2
# Log in and grab CSRF token:
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt http://127.0.0.1:8000/login/ > /tmp/login.html
CSRF=$(grep csrfmiddlewaretoken /tmp/login.html | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
curl -s -X POST http://127.0.0.1:8000/login/ \
  -d "username=admin&password=admin&csrfmiddlewaretoken=$CSRF" \
  -b /tmp/cookies.txt -c /tmp/cookies.txt -H "Referer: http://127.0.0.1:8000/login/"
# Approve a real PR (replace N with an open PR number on PT's repo):
curl -s http://127.0.0.1:8000/catalog/ -b /tmp/cookies.txt -c /tmp/cookies.txt > /tmp/catalog.html
CSRF=$(grep csrfmiddlewaretoken /tmp/catalog.html | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
curl -s -X POST http://127.0.0.1:8000/policies/approve/ \
  -d "pr_number=N&csrfmiddlewaretoken=$CSRF" \
  -b /tmp/cookies.txt -c /tmp/cookies.txt -H "Referer: http://127.0.0.1:8000/catalog/" \
  -L
kill $SERVER_PID
```

Expected: the PR on GitHub shows a new "APPROVED" review by the PolicyCodex GitHub App. The browser response includes a "PR #N approved." flash on the catalog page.

If no live PR is available or credentials are not local, SKIP this step. The unit tests are authoritative.

- [ ] **Step 3: Confirm clean branch + commit history**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 5 commits since BASE `5017488`:

1. `feat(APP-18): add approve_pr to GitProvider ABC + base-class tests`
2. `feat(APP-18): GitHubProvider.approve_pr via PyGithub create_review`
3. `feat(APP-18): approve_pr view scaffold (URL, auth, POST-only, input validation)`
4. `feat(APP-18): approve_pr view gate-guard + provider call + audit log`
5. `feat(APP-18): approve-PR form on catalog (UI surface for the approve action)`

If counts differ (e.g., Step 6 of Task 5 added a flash-rendering edit to `base.html` as part of commit 4, not a separate commit), surface in the self-report.

- [ ] **Step 4: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list with messages.
- Test count before / after (expect 180 → 198).
- `manage.py check` result.
- Smoke result (Step 2): PASS / SKIPPED / FAIL with notes.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.

- [ ] **Step 5: Handoff**

Do not merge to main. Do not push. The dispatching session (Scarlet) will route the branch through spec-compliance review and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `app/git_provider/base.py` declares `approve_pr(pr_number, working_dir, body="") -> dict` as an `@abstractmethod`.
- `app/git_provider/github_provider.py` implements `approve_pr` by calling `Repository.get_pull(pr_number).create_review(body=body, event="APPROVE")` and returning `{"review_id", "state", "pr_number"}`.
- `app/git_provider/tests/test_base.py` adds `test_subclass_missing_approve_pr_fails` AND adds a stub `approve_pr` method to every other `IncompleteProvider`.
- `app/git_provider/tests/test_github_provider.py` adds 4 tests: APPROVE-event call, default-empty-body, origin-lookup-failure, PyGithub-exception propagation.
- `core/views.py` adds `approve_pr(request)` decorated with `@login_required` and `@require_POST`, with: pr_number parsing, working-copy-config lookup, gate-guard on `read_pr_state == "drafted"`, success path call to `provider.approve_pr`, error flashes via `django.contrib.messages`, audit log lines including the Django username and PR number.
- `core/urls.py` adds `path("policies/approve/", views.approve_pr, name="approve_pr")`.
- `core/templates/catalog.html` adds a POST form with a numeric `pr_number` input, CSRF token, and submit button, ONLY in the non-empty-onboarding branch.
- `core/tests/test_approve_pr.py` has 11 tests: URL resolves, login required, GET rejected (405), missing pr_number, non-numeric pr_number, happy-path (provider called + flash + audit log), 3 non-drafted-state parametrized refusals, working-copy-unconfigured flash, provider-exception flash.
- `core/tests/test_catalog.py` adds 2 tests: approve form present in non-empty state, approve form absent in empty-onboarding state.
- Full repo test suite: 180 → 198 passing.
- `manage.py check` exits 0.
- 5 commits on the branch since BASE `5017488`, all with `APP-18` in the message.
- No edits outside the 8 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt`, `PT`, `pensacola`, `tallahassee`) in any of the 8 files. PT names appear ONLY in the optional smoke env exports in Task 7 Step 2.

---

## Self-Review

**Spec coverage:**
- Ticket title "Approve action in UI calls GitHub review API on behalf of authenticated reviewer" → Task 3 (provider) + Task 4-5 (view) + Task 6 (UI button) ✓
- "GitHub review API" → Task 3 calls `pr.create_review(body=body, event="APPROVE")` per the PyGithub `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` endpoint (confirmed via Context7) ✓
- "on behalf of authenticated reviewer" → GitHub-side actor is the App installation token (per `_build_installation_token` in `github_provider.py`); Django-side actor is logged in `logger.info` lines ✓
- CLAUDE.md gate model "Reviewed = PR approved" → APP-18 is the action that flips Drafted → Reviewed; the gate-guard ensures we only act on Drafted ✓
- Depends on APP-04 → uses `GitHubProvider` directly, no new provider work outside `approve_pr` ✓
- Ship-generic → no PT tokens in any production file; fixtures use synthetic slugs only ✓

**Placeholder scan:** No "TBD", no "TODO" in production code (the Task 4 stub message "not yet wired" is replaced in Task 5; the comment about APP-17 wiring per-row buttons is descriptive, not a placeholder). Every step has a code block where code is needed. Every test has assertions. Every error path has a flash message.

**Type consistency:**
- `approve_pr` signature consistent across `base.py`, `github_provider.py`, `test_base.py` stubs, `test_github_provider.py` mocks, and the view's call site: `(pr_number: int, working_dir: Path, body: str = "") -> dict`.
- Return dict shape `{"review_id": int, "state": str, "pr_number": int}` consistent across the implementation, the provider tests, and the view's `result.get("review_id")` audit log.
- URL name `approve_pr` consistent across `urls.py`, `reverse("approve_pr")` in tests, and the (no) `{% url %}` calls (the template uses a hardcoded `/policies/approve/` per the existing catalog-template convention).
- Gate-guard string `"drafted"` matches the value returned by `GitHubProvider.read_pr_state` (per `github_provider.py:235-256`).
- `provider.approve_pr` called with keyword args `pr_number=`, `working_dir=`, `body=` in both the implementation and test assertions; positional vs keyword consistency maintained.

**Potential gotcha (flagged in plan):** Task 5 Step 6 conditionally adds a `{% messages %}` block to `base.html` if the flash-assertion tests fail. The implementer must run the Step 4 test first to determine whether the edit is needed before committing.

No other issues found.
