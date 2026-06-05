# APP-16 Onboarding Configuration Commit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize onboarding by persisting the wizard's choices as `.policycodex/config.yaml` and committing it together with the APP-15 `policies/document-retention/` bundle to the diocese policy repo in a single pull request.

**Architecture:** A new Django-free module `app/onboarding/finalize.py` serializes `WizardState.all_data()` to YAML (excluding secret-named fields), writes it into the working copy, then runs the established `branch → commit → push → open_pr` provider sequence (the same shape as `core/views.py:policy_edit`). The screen-7 `accept` handler (`app/onboarding/retention_policy.py`) calls it after scaffolding the bundle. The commit stages only the two explicit paths (`.policycodex/config.yaml` and the bundle directory); it never runs `git add .`, so the onboarding staging dir (`.policycodex-staging/`) and the raw uploaded PDF never reach the repo.

**Key design decisions (locked):**
- **One PR, not two.** Config file and the foundational bundle ship in the same onboarding PR (matches the foundational-policy design: "both reviewed in the same PR").
- **Secrets stay local.** `build_config_yaml` drops any field whose key marks it a credential (token/api_key/secret/password/credential). The GitHub token and LLM API key live in `~/.config/policycodex/`, never the repo. This is the one validation guard in this ticket and it is justified: writing a committed file is exactly the boundary where a secret could leak.
- **Scoped staging.** `provider.commit(files=[...])` runs `git add <path>` once per explicit path. Passing the bundle *directory* stages its three files (`policy.md`, `data.yaml`, `source.pdf`) and nothing else.
- **Branch name is not slug-mapped.** The onboarding branch is `policycodex/onboarding-<hex>`, so `branch_to_slug` returns `None` and the catalog's per-slug gate lookup ignores it (this PR is repo initialization, not a single-policy edit). Until the PR merges, the catalog renders `document-retention` with the default "published" badge — a minor, acceptable cosmetic inaccuracy for the bootstrap window. Do not try to slug-map a multi-file init PR.
- **Provider failure degrades, never 500s.** On a provider error the bundle stays scaffolded locally, the step is NOT marked complete, and the review screen re-renders with an error (mirrors `policy_edit`'s "saved locally, ask admin to retry").

**Tech Stack:** Python 3, Django 5, PyYAML, pytest / pytest-django. Test interpreter: `ai/venv/bin/python -m pytest` (no root venv).

---

## File Structure

- **Create** `app/onboarding/finalize.py` — config serialization (`build_config_yaml`), file write (`write_config_file`), branch naming (`make_onboarding_branch_name`), and the `finalize_onboarding` orchestrator. Django-free; takes the provider as a parameter so it is trivially unit-testable.
- **Create** `app/onboarding/tests/test_finalize.py` — unit tests for the four functions above (pure + fake-provider).
- **Modify** `app/onboarding/retention_policy.py` — wire `finalize_onboarding` into the `accept` action; add imports.
- **Modify** `app/onboarding/tests/test_onboarding_views.py` — add a `stub_git_provider` fixture, apply it to the two existing accept tests (which currently hit no provider and would otherwise break), and add two new integration tests.
- **Create** `repo-template/.gitignore` — defense-in-depth ignore of `.policycodex-staging/` for newly-created diocese repos.

---

### Task 1: Config serialization with secret scrubbing

**Files:**
- Create: `app/onboarding/finalize.py`
- Test: `app/onboarding/tests/test_finalize.py`

- [ ] **Step 1: Write the failing tests**

Create `app/onboarding/tests/test_finalize.py`:

```python
"""Unit tests for onboarding finalization (APP-16)."""
import yaml

from app.onboarding.finalize import build_config_yaml


def test_build_config_yaml_emits_steps_in_wizard_order():
    all_data = {
        # Deliberately out of wizard order; output must be re-ordered.
        "address-scheme": {"scheme": "chapter-section-item"},
        "github-repo": {"mode": "connect", "repo_url": "https://github.com/d/r", "branch": "main"},
    }
    doc = yaml.safe_load(build_config_yaml(all_data))
    assert doc["schema_version"] == 1
    assert list(doc["onboarding"].keys()) == ["github-repo", "address-scheme"]
    assert doc["onboarding"]["github-repo"]["repo_url"] == "https://github.com/d/r"


def test_build_config_yaml_excludes_secret_fields():
    all_data = {"llm-provider": {"provider": "claude", "api_key": "sk-x", "auth_token": "t"}}
    doc = yaml.safe_load(build_config_yaml(all_data))
    assert doc["onboarding"]["llm-provider"] == {"provider": "claude"}


def test_build_config_yaml_omits_steps_not_in_data():
    doc = yaml.safe_load(build_config_yaml({}))
    assert doc["onboarding"] == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.onboarding.finalize'`.

- [ ] **Step 3: Write the minimal implementation**

Create `app/onboarding/finalize.py`:

```python
"""Finalize onboarding: commit the diocese config + first foundational bundle.

The wizard collects per-screen choices into WizardState. On the final "accept"
of screen 7, this module serializes those choices to `.policycodex/config.yaml`
in the working copy and opens a single PR that contains both the config file and
the scaffolded `policies/document-retention/` bundle (written by
app.onboarding.scaffold in APP-15).

Secrets never reach the repo: build_config_yaml drops any key whose name marks
it as a credential (the GitHub token and LLM API key live in
~/.config/policycodex/, per project convention). The commit stages only the
explicit paths passed to the provider; it never runs `git add .`, so the
onboarding staging dir and the raw uploaded PDF are never swept into the repo.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from app.onboarding import wizard

CONFIG_SCHEMA_VERSION = 1
CONFIG_DIR_NAME = ".policycodex"
CONFIG_FILE_NAME = "config.yaml"

# A wizard field is treated as a secret (and excluded from the committed config)
# when its key contains any of these markers. Keeps credentials out of the repo
# as future screens (e.g. llm-provider) add an api_key field.
_SECRET_KEY_MARKERS = (
    "token", "secret", "password", "api_key", "apikey", "credential",
)


def _is_secret_key(key: str) -> bool:
    low = str(key).lower()
    return any(marker in low for marker in _SECRET_KEY_MARKERS)


def _scrub_secrets(step_data: dict) -> dict:
    return {k: v for k, v in step_data.items() if not _is_secret_key(k)}


def build_config_yaml(all_data: dict) -> str:
    """Serialize wizard choices to YAML for committing to the policy repo.

    Steps are emitted in wizard order for stable diffs; secret-named fields are
    dropped; only steps present in `all_data` appear.
    """
    onboarding: dict = {}
    for step in wizard.STEPS:
        if step.slug in all_data:
            onboarding[step.slug] = _scrub_secrets(all_data[step.slug])
    doc = {"schema_version": CONFIG_SCHEMA_VERSION, "onboarding": onboarding}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/finalize.py app/onboarding/tests/test_finalize.py
git commit -m "feat(APP-16): serialize wizard choices to config YAML, scrub secrets"
```

---

### Task 2: Config file write + branch naming

**Files:**
- Modify: `app/onboarding/finalize.py`
- Test: `app/onboarding/tests/test_finalize.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/onboarding/tests/test_finalize.py`:

```python
from app.onboarding.finalize import make_onboarding_branch_name, write_config_file


def test_write_config_file_creates_dir_and_returns_path(tmp_path):
    p = write_config_file(tmp_path, "schema_version: 1\n")
    assert p == tmp_path / ".policycodex" / "config.yaml"
    assert p.read_text(encoding="utf-8") == "schema_version: 1\n"


def test_write_config_file_appends_trailing_newline(tmp_path):
    p = write_config_file(tmp_path, "a: b")
    assert p.read_text(encoding="utf-8").endswith("\n")


def test_make_onboarding_branch_name_is_prefixed_and_unique():
    a = make_onboarding_branch_name()
    b = make_onboarding_branch_name()
    assert a.startswith("policycodex/onboarding-")
    assert a != b
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py -v`
Expected: FAIL with `ImportError: cannot import name 'make_onboarding_branch_name'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `app/onboarding/finalize.py` (after `build_config_yaml`):

```python
def write_config_file(working_dir: Path, config_yaml_text: str) -> Path:
    """Write `.policycodex/config.yaml` under the working copy. Returns its path."""
    config_dir = Path(working_dir) / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_FILE_NAME
    text = config_yaml_text if config_yaml_text.endswith("\n") else config_yaml_text + "\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def make_onboarding_branch_name() -> str:
    """policycodex/onboarding-<short-uuid>. Distinct from edit branches so the
    catalog's slug-mapped gate lookup ignores it (this PR is repo init, not a
    single-policy edit)."""
    return f"policycodex/onboarding-{uuid.uuid4().hex[:8]}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/finalize.py app/onboarding/tests/test_finalize.py
git commit -m "feat(APP-16): write config file to working copy, name onboarding branch"
```

---

### Task 3: The `finalize_onboarding` orchestrator

**Files:**
- Modify: `app/onboarding/finalize.py`
- Test: `app/onboarding/tests/test_finalize.py`

- [ ] **Step 1: Write the failing test**

Append to `app/onboarding/tests/test_finalize.py`:

```python
from app.onboarding.finalize import finalize_onboarding


class _FakeProvider:
    def __init__(self):
        self.calls = []

    def branch(self, name, working_dir):
        self.calls.append(("branch", name))

    def commit(self, *, message, files, author_name, author_email, working_dir):
        self.calls.append(("commit", list(files)))
        return "deadbeef"

    def push(self, branch, working_dir):
        self.calls.append(("push", branch))

    def open_pr(self, *, title, body, head_branch, base_branch, working_dir):
        self.calls.append(("open_pr", head_branch, base_branch))
        return {"pr_number": 7, "url": "https://github.com/d/r/pull/7", "state": "drafted"}


def test_finalize_sequences_writes_config_and_scopes_commit(tmp_path):
    bundle_dir = tmp_path / "policies" / "document-retention"
    bundle_dir.mkdir(parents=True)
    provider = _FakeProvider()

    pr = finalize_onboarding(
        working_dir=tmp_path,
        config_yaml_text="schema_version: 1\n",
        bundle_dir=bundle_dir,
        provider=provider,
        author_name="A",
        author_email="a@x",
        base_branch="main",
        username="admin",
    )

    assert pr["pr_number"] == 7
    assert [c[0] for c in provider.calls] == ["branch", "commit", "push", "open_pr"]

    commit_files = [c for c in provider.calls if c[0] == "commit"][0][1]
    assert tmp_path / ".policycodex" / "config.yaml" in commit_files
    assert bundle_dir in commit_files
    assert all(".policycodex-staging" not in str(f) for f in commit_files)

    # open_pr targets the configured base branch.
    open_pr_call = [c for c in provider.calls if c[0] == "open_pr"][0]
    assert open_pr_call[2] == "main"

    # The config file was actually written to disk.
    assert (tmp_path / ".policycodex" / "config.yaml").is_file()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py::test_finalize_sequences_writes_config_and_scopes_commit -v`
Expected: FAIL with `ImportError: cannot import name 'finalize_onboarding'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `app/onboarding/finalize.py`:

```python
def finalize_onboarding(
    *,
    working_dir: Path,
    config_yaml_text: str,
    bundle_dir: Path,
    provider,
    author_name: str,
    author_email: str,
    base_branch: str,
    username: str,
) -> dict:
    """Write the config file, then branch -> commit -> push -> open PR.

    Commits exactly [config_path, bundle_dir]; never `git add .`. Returns the PR
    metadata dict from the provider. Any provider exception propagates to the
    caller, which is responsible for the user-facing degrade.
    """
    config_path = write_config_file(working_dir, config_yaml_text)
    branch_name = make_onboarding_branch_name()
    message = "Initialize diocese configuration and document-retention policy"

    provider.branch(branch_name, working_dir)
    provider.commit(
        message=message,
        files=[config_path, bundle_dir],
        author_name=author_name,
        author_email=author_email,
        working_dir=working_dir,
    )
    provider.push(branch_name, working_dir)
    pr_body = (
        f"Opened by PolicyCodex during onboarding on behalf of {username}.\n\n"
        f"Contents:\n"
        f"- {CONFIG_DIR_NAME}/{CONFIG_FILE_NAME} (diocese configuration)\n"
        f"- policies/{bundle_dir.name}/ (document-retention foundational policy)\n"
    )
    return provider.open_pr(
        title="Initialize policy repository",
        body=pr_body,
        head_branch=branch_name,
        base_branch=base_branch,
        working_dir=working_dir,
    )
```

- [ ] **Step 4: Run the full finalize test module to verify it passes**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_finalize.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app/onboarding/finalize.py app/onboarding/tests/test_finalize.py
git commit -m "feat(APP-16): finalize_onboarding orchestrates scoped commit + PR"
```

---

### Task 4: Wire finalize into the screen-7 `accept` action

**Files:**
- Modify: `app/onboarding/retention_policy.py:23-33` (imports) and `:156-171` (the `accept` block)
- Test: `app/onboarding/tests/test_onboarding_views.py`

Note: the two existing accept tests (`test_last_step_continue_completes_and_redirects_to_catalog` at ~line 105 and `test_screen7_accept_scaffolds_bundle_and_finishes` at ~line 243) currently exercise `accept` with NO git provider. Once finalize is wired they would construct a real `GitHubProvider()` and fail. This task adds a `stub_git_provider` fixture and applies it to both, plus two new tests. Implement the test changes and the source change together so the suite stays green.

- [ ] **Step 1: Write/adjust the failing tests**

In `app/onboarding/tests/test_onboarding_views.py`, add this fixture immediately after the `stub_extraction` fixture (after ~line 193):

```python
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
```

Update the two existing accept tests to request the new fixture. Change their signatures:

```python
def test_last_step_continue_completes_and_redirects_to_catalog(client, user, working_copy, stub_extraction, stub_git_provider):
```

```python
def test_screen7_accept_scaffolds_bundle_and_finishes(client, user, working_copy, stub_extraction, stub_git_provider):
```

(Their bodies are unchanged.)

Then append two new tests at the end of the file:

```python
def test_screen7_accept_commits_config_and_opens_pr(client, user, working_copy, stub_extraction, stub_git_provider):
    import yaml

    client.force_login(user)
    _advance_to_retention_policy(client)
    upload = SimpleUploadedFile("retention.pdf", b"%PDF-1.4", content_type="application/pdf")
    client.post("/onboarding/retention-policy/", {"action": "extract", "pdf_file": upload})
    resp = client.post("/onboarding/retention-policy/", {"action": "accept"})

    assert resp.status_code == 302
    assert resp.url == "/catalog/"

    # working_copy is tmp_path/policies/policies; the working_dir is its parent.
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

    # Staging dir cleared on success.
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

    # Degrades to the review screen, not a 500 or a redirect.
    assert resp.status_code == 200
    assert "Administrative" in resp.content.decode()
    # The bundle is still saved locally for a retry.
    assert (working_copy / "document-retention" / "data.yaml").is_file()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -v`
Expected: The two new tests FAIL (config file not written / still redirects). `test_screen7_accept_provider_failure...` fails because today's handler has no provider call so it redirects 302 instead of re-rendering 200.

- [ ] **Step 3: Update the imports in `app/onboarding/retention_policy.py`**

After the existing import block (the imports currently end around line 33 with `from ingest.extractors import extract as extract_text`), add:

```python
from app.git_provider.github_provider import GitHubProvider
from app.onboarding.finalize import build_config_yaml, finalize_onboarding
from core.git_identity import get_git_author
```

(`load_working_copy_config` is already imported.)

- [ ] **Step 4: Rewrite the `accept` block**

Replace the entire `if action == "accept":` block (currently lines ~156-171) with:

```python
    if action == "accept":
        draft = _load_draft(staging)
        if draft is None:
            return _render_upload(request, target, state)
        bundle_dir = scaffold_retention_bundle(
            policies_dir,
            title=draft["title"],
            owner=draft["owner"],
            narrative=_NARRATIVE_STUB,
            data_yaml_text=draft["data_yaml"],
            source_pdf=staging / "source.pdf" if (staging / "source.pdf").is_file() else None,
        )
        config = load_working_copy_config()
        author_name, author_email = get_git_author(request.user)
        config_yaml_text = build_config_yaml(state.all_data())
        try:
            pr = finalize_onboarding(
                working_dir=config.working_dir,
                config_yaml_text=config_yaml_text,
                bundle_dir=bundle_dir,
                provider=GitHubProvider(),
                author_name=author_name,
                author_email=author_email,
                base_branch=config.branch,
                username=request.user.get_username(),
            )
        except (RuntimeError, ValueError) as exc:
            logger.error("APP-16 onboarding finalize failed: %s", exc)
            messages.error(
                request,
                "Couldn't publish your configuration to the policy repository. "
                "Your choices are saved locally; ask your administrator to retry.",
            )
            return _render_review(request, target, state, draft)
        shutil.rmtree(staging, ignore_errors=True)
        state.mark_complete(STEP_SLUG)
        messages.success(
            request,
            f"Onboarding complete. Configuration pull request opened: {pr.get('url', '')}",
        )
        return redirect("catalog")
```

- [ ] **Step 5: Run the onboarding view tests to verify they pass**

Run: `ai/venv/bin/python -m pytest app/onboarding/tests/test_onboarding_views.py -v`
Expected: PASS (all, including the two updated and two new tests).

- [ ] **Step 6: Commit**

```bash
git add app/onboarding/retention_policy.py app/onboarding/tests/test_onboarding_views.py
git commit -m "feat(APP-16): commit config + bundle PR on onboarding accept"
```

---

### Task 5: Defense-in-depth gitignore for the staging dir

The commit is already scoped to explicit paths, so the staging dir cannot leak through this code path. This task adds a vendored `.gitignore` for newly-created diocese repos so manual `git add .` by an operator also cannot sweep the scratch dir. Connect-mode (existing) repos rely on the explicit-path guarantee in `finalize_onboarding`.

**Files:**
- Create: `repo-template/.gitignore`

- [ ] **Step 1: Create the file**

Create `repo-template/.gitignore`:

```gitignore
# PolicyCodex onboarding scratch space - never commit. The app stages an
# uploaded retention PDF and an extraction draft here during the wizard. The app
# only ever `git add`s explicit paths, so this is defense-in-depth for any
# manual git use in the diocese repo.
.policycodex-staging/
```

- [ ] **Step 2: Verify the entry is present**

Run: `grep -n '.policycodex-staging/' repo-template/.gitignore`
Expected: prints the matching line.

- [ ] **Step 3: Commit**

```bash
git add repo-template/.gitignore
git commit -m "chore(APP-16): vendor .gitignore ignoring onboarding staging dir"
```

---

### Final verification (after all tasks)

- [ ] **Step 1: Run the full suite**

Run: `ai/venv/bin/python -m pytest -q`
Expected: all tests pass (the suite count grows by the seven new finalize tests + two new view tests).

- [ ] **Step 2: Confirm no `git add .` slipped in**

Run: `grep -rn "git add" app/onboarding/`
Expected: no matches in onboarding source (staging is done by `provider.commit`, which adds explicit paths only).

---

## Self-Review

**Spec coverage (APP-16 = "Configuration commit: persist wizard choices as a config file in the policy repo", with the note to scope `git add` to `policies/` + the config file, never `git add .`):**
- "Persist wizard choices as a config file" → Task 1 (`build_config_yaml`) + Task 2 (`write_config_file`) write `.policycodex/config.yaml` from `WizardState.all_data()`. Covered.
- "in the policy repo" → Task 3 (`finalize_onboarding`) commits + pushes + opens a PR; Task 4 wires it into the onboarding accept. Covered.
- "scope this commit's `git add` ... do NOT `git add .` ... staging dir and source.pdf never swept in" → Task 3 passes `files=[config_path, bundle_dir]` only; `provider.commit` runs `git add <path>` per entry; Task 3 and Task 4 tests assert no `.policycodex-staging` path is committed; Task 5 adds a belt-and-suspenders ignore. Covered.
- The APP-15 deferral ("commit-to-repo deferred to APP-16") → the bundle dir is committed in the same PR. Covered.

**Placeholder scan:** No TBD/TODO/"handle errors appropriately"/"similar to Task N". Every code step shows full code; the one `except` clause is concrete with a logged message and a user-facing degrade.

**Type consistency:** `build_config_yaml(all_data: dict) -> str`, `write_config_file(working_dir, text) -> Path`, `make_onboarding_branch_name() -> str`, and `finalize_onboarding(*, working_dir, config_yaml_text, bundle_dir, provider, author_name, author_email, base_branch, username) -> dict` are used identically in tests and in the `accept` handler. `scaffold_retention_bundle` returns the bundle `Path` (confirmed in `app/onboarding/scaffold.py:50`), which Task 4 captures as `bundle_dir` and forwards. Provider method shapes match `app/git_provider/base.py` (`branch(name, working_dir)`, `commit(message, files, author_name, author_email, working_dir)`, `push(branch, working_dir)`, `open_pr(title, body, head_branch, base_branch, working_dir)`).
