# APP-21 App Startup Self-Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Django system-check that validates every required `provides:` capability (`classifications`, `retention-schedule`) is satisfied by exactly one published foundational policy in the local working copy. Failure refuses to serve and points the admin at the broken file.

**Architecture:** New module `app/working_copy/checks.py` registers a single check function via Django's check framework (`django.core.checks.register`). The function reuses APP-05's `load_working_copy_config` and INGEST-07's `BundleAwarePolicyReader`. A new `POLICYCODEX_ONBOARDING_COMPLETE` setting gates the severity of "working copy not present yet" (Warning during onboarding; Error post-onboarding). Bundle validity failures (broken `data.yaml`, missing or duplicate capability provider) are always Error regardless of onboarding state.

**Tech Stack:** Django 5+ system-check framework, Python 3.12, pytest-django.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-21 (L3 of the four-layer foundational-policy protection model). Design: `internal/PolicyWonk-Foundational-Policy-Design.md` lines 138-140.

**BASE:** `main` at SHA `f6a65d3` (post-Wave-1 close, post-recipe docs).

**Discipline reminders:**
- TDD: every test in this plan must be observed-failing first, then passing. Don't skip RED.
- No em dashes anywhere in new content (code, docstrings, comments, commit messages).
- `>=` floor pins in any requirements file (none needed here).
- Ship-generic: no `pt`, `PT`, `pensacola`, `tallahassee` tokens in code or test fixtures. Tests use synthetic bundles built via `tmp_path`.

---

## File Structure

- Create: `app/working_copy/apps.py` — `WorkingCopyAppConfig(AppConfig)` with `default_auto_field` and `ready()` that imports the checks module. Class name is deliberately NOT `WorkingCopyConfig` to avoid colliding with the existing dataclass in `app/working_copy/config.py`.
- Create: `app/working_copy/checks.py` — `foundational_policy_check(app_configs, **kwargs)` registered with `@register()`; module-level constants `REQUIRED_CAPABILITIES`, error-id strings; helper `_is_onboarding_complete()` that parses the truthy envvar correctly.
- Create: `app/working_copy/tests/test_checks.py` — 11 pytest tests covering happy path, capability errors, broken-bundle, missing-working-copy + onboarding gate (both modes), unset env var + onboarding gate (both modes).
- Modify: `policycodex_site/settings.py` — add `'app.working_copy.apps.WorkingCopyAppConfig'` to `INSTALLED_APPS` (line 42-50, currently lists only Django built-ins + `'core'`); add `POLICYCODEX_ONBOARDING_COMPLETE` env-driven setting alongside the existing `POLICYCODEX_*` block from APP-05.

No other files touched. `app/working_copy/config.py`, `app/working_copy/manager.py`, `ingest/policy_reader.py` are stable from Wave-1 and must NOT be modified.

---

## Task 1: Worktree pre-flight

**Files:**
- None modified.

- [ ] **Step 1: Confirm worktree state**

Run:

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

Expected: BASE SHA is `f6a65d3` or a descendant; branch is the auto-worktree branch the harness gave you (something like `worktree-agent-<id>`); status is clean.

If anything is unexpected, STOP and report.

- [ ] **Step 2: Merge `main` into your worktree branch**

The harness's auto-worktree may have branched from a session-start commit older than current `main`. Run:

```bash
git fetch
git merge main --no-edit
```

Expected: either "Already up to date." or a clean fast-forward to `f6a65d3` (or descendant). If a merge conflict surfaces, STOP and report (something is wrong with the harness state).

- [ ] **Step 3: Confirm baseline test suite is green**

Run:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `156 passed`.

- [ ] **Step 4: Confirm Django settings + INSTALLED_APPS current state**

Run:

```bash
grep -n "INSTALLED_APPS\|app.working_copy" /Users/chuck/PolicyWonk/policycodex_site/settings.py | head -5
```

Expected output includes line 42 (`INSTALLED_APPS = [`) and NO match for `app.working_copy` (this task adds it). If `app.working_copy` is already in settings, STOP and report.

- [ ] **Step 5: No commit yet.**

---

## Task 2: AppConfig wiring + INSTALLED_APPS + ONBOARDING setting (TDD)

**Files:**
- Create: `app/working_copy/apps.py`
- Modify: `policycodex_site/settings.py`
- Create: `app/working_copy/tests/test_checks.py`

- [ ] **Step 1: Write the failing test**

Create `app/working_copy/tests/test_checks.py`:

```python
"""Tests for the foundational-policy startup check."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps as django_apps
from django.test import override_settings


def test_working_copy_app_is_installed():
    """app.working_copy must be in INSTALLED_APPS for the check to register."""
    app_labels = {app.label for app in django_apps.get_app_configs()}
    assert "working_copy" in app_labels


def test_working_copy_app_config_class_name():
    """The AppConfig subclass must NOT be named WorkingCopyConfig (collides with the
    dataclass of the same name in app/working_copy/config.py)."""
    cfg = django_apps.get_app_config("working_copy")
    assert type(cfg).__name__ == "WorkingCopyAppConfig"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -10
```

Expected: `LookupError: No installed app with label 'working_copy'.` for both tests.

- [ ] **Step 3: Create `app/working_copy/apps.py`**

Write:

```python
"""Django AppConfig for the working_copy app.

The class is named WorkingCopyAppConfig (NOT WorkingCopyConfig) to avoid
colliding with the WorkingCopyConfig dataclass in app/working_copy/config.py.
Django auto-discovers the checks module via the ready() hook below.
"""
from django.apps import AppConfig


class WorkingCopyAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.working_copy"
    label = "working_copy"

    def ready(self) -> None:
        # Import the checks module so its @register() decorators run on app load.
        from app.working_copy import checks  # noqa: F401
```

- [ ] **Step 4: Add `POLICYCODEX_ONBOARDING_COMPLETE` to settings**

Open `policycodex_site/settings.py`. Find the existing `POLICYCODEX_*` block (added by APP-05; should be near the top of the file after `BASE_DIR`). Add immediately below it:

```python
# Onboarding state (APP-21). When False, the startup self-check downgrades
# "working copy missing" failures to Warnings (lets `manage.py runserver`
# start during the wizard). The wizard (APP-15) flips this to True when
# the user completes setup. Truthy parser tolerates "1", "true", "yes"
# (case-insensitive); empty string and "0"/"false"/"no" are falsy.
_onboarding_raw = os.environ.get("POLICYCODEX_ONBOARDING_COMPLETE", "")
POLICYCODEX_ONBOARDING_COMPLETE = _onboarding_raw.lower() in ("1", "true", "yes")
```

If `import os` is not yet present in the file, the existing APP-05 settings block should have added it. Verify by searching:

```bash
grep -n "^import os" /Users/chuck/PolicyWonk/policycodex_site/settings.py
```

Expected: one match. If zero matches, add `import os` at the top of the file alongside the existing `from pathlib import Path`.

- [ ] **Step 5: Add `app.working_copy` to INSTALLED_APPS**

Edit `policycodex_site/settings.py` line 42-50. Change from:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]
```

to:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'app.working_copy.apps.WorkingCopyAppConfig',
]
```

The explicit class path tells Django to use the named AppConfig (rather than auto-discovering a default).

- [ ] **Step 6: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -5
```

Expected: 2 passing.

- [ ] **Step 7: Full repo test suite still green**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `158 passed` (156 baseline + 2 new). Capture the number.

- [ ] **Step 8: Commit**

```bash
git add app/working_copy/apps.py policycodex_site/settings.py app/working_copy/tests/test_checks.py
git commit -m "feat(APP-21): WorkingCopyAppConfig + ONBOARDING_COMPLETE setting + INSTALLED_APPS wire-up"
```

Verify with `git log --oneline -1`.

---

## Task 3: Stub check + registration (TDD)

**Files:**
- Create: `app/working_copy/checks.py`
- Modify: `app/working_copy/tests/test_checks.py`

- [ ] **Step 1: Write the failing test**

Append to `app/working_copy/tests/test_checks.py`:

```python
def test_foundational_policy_check_is_registered():
    """The check function must be registered with Django's check framework."""
    from django.core.checks import registry
    check_names = {fn.__name__ for fn in registry.registry.get_checks()}
    assert "foundational_policy_check" in check_names


def test_check_runs_via_manage_py_check_command(monkeypatch):
    """`manage.py check` should invoke our check and not crash."""
    from django.core.management import call_command
    from io import StringIO

    # Use the onboarding-mode default (False) and clear repo URL so the
    # check returns a Warning rather than an Error (which would set exit
    # code 1 and make this assertion noisier).
    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        out = StringIO()
        # call_command raises SystemExit on Error-level findings; the
        # onboarding-mode Warning path keeps it quiet.
        call_command("check", stdout=out)
    # No assertion on output content here; the goal is "command ran".
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py::test_foundational_policy_check_is_registered -v 2>&1 | tail -10
```

Expected: AssertionError (the check is not yet registered).

- [ ] **Step 3: Create `app/working_copy/checks.py`**

Write:

```python
"""Foundational-policy startup self-check (APP-21).

Validates that every required `provides:` capability is satisfied by
exactly one published foundational policy in the local working copy.

Failure severity is gated by the POLICYCODEX_ONBOARDING_COMPLETE setting:
- False (default): missing working copy or unset repo URL returns Warning,
  letting `manage.py runserver` start during the seven-screen onboarding
  wizard. Bundle-validity failures (broken data.yaml, missing or duplicate
  capability provider) are always Error.
- True: all failures are Error and the app refuses to serve.
"""
from __future__ import annotations

from typing import Sequence

from django.conf import settings
from django.core.checks import Error, Warning, register


REQUIRED_CAPABILITIES: tuple[str, ...] = ("classifications", "retention-schedule")


@register()
def foundational_policy_check(app_configs, **kwargs) -> Sequence:
    """Return a list of Error/Warning objects; empty list means pass."""
    # Stub: real logic lands in Task 4 onwards. Return [] so the registration
    # smoke tests in Task 3 pass without false-positive failures.
    return []
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -8
```

Expected: 4 passing (the 2 from Task 2 plus 2 new).

- [ ] **Step 5: Confirm `manage.py check` runs cleanly from the shell**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues (0 silenced).` and exit code 0.

- [ ] **Step 6: Commit**

```bash
git add app/working_copy/checks.py app/working_copy/tests/test_checks.py
git commit -m "feat(APP-21): foundational_policy_check stub + Django registration"
```

---

## Task 4: Happy path + missing-capability + duplicate-capability detection (TDD)

**Files:**
- Modify: `app/working_copy/checks.py`
- Modify: `app/working_copy/tests/test_checks.py`

- [ ] **Step 1: Write the failing tests**

Append to `app/working_copy/tests/test_checks.py`:

```python
def _stub_logical_policy(
    *,
    slug: str = "retention",
    foundational: bool = True,
    provides: tuple[str, ...] = ("classifications", "retention-schedule"),
    policy_path: Path | None = None,
):
    """Build a stand-in for an ingest.policy_reader.LogicalPolicy."""
    from ingest.policy_reader import LogicalPolicy
    pp = policy_path or Path(f"/tmp/policies/{slug}/policy.md")
    return LogicalPolicy(
        slug=slug,
        kind="bundle",
        policy_path=pp,
        data_path=pp.parent / "data.yaml",
        frontmatter={},
        body="",
        foundational=foundational,
        provides=provides,
    )


def _run_check_with_mocked_reader(*, policies, onboarding=True, repo_url="https://example.com/x.git"):
    """Invoke the check with a mocked BundleAwarePolicyReader yielding `policies`."""
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=onboarding,
        POLICYCODEX_POLICY_REPO_URL=repo_url,
        POLICYCODEX_POLICY_BRANCH="main",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.return_value = iter(policies)
                return checks_module.foundational_policy_check(app_configs=None)


def test_happy_path_returns_no_errors():
    """One foundational policy providing both required capabilities passes."""
    policies = [_stub_logical_policy()]
    results = _run_check_with_mocked_reader(policies=policies)
    assert results == []


def test_missing_capability_returns_error_with_hint():
    """A foundational policy providing only one of two required capabilities fails."""
    policies = [
        _stub_logical_policy(provides=("classifications",))  # missing "retention-schedule"
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    assert len(results) == 1
    err = results[0]
    from django.core.checks import Error
    assert isinstance(err, Error)
    assert err.id == "policycodex.E002"
    assert "retention-schedule" in err.msg
    assert "foundational: true" in err.hint


def test_two_missing_capabilities_returns_two_errors():
    """Multiple missing capabilities surface as separate Error entries."""
    policies = [
        _stub_logical_policy(provides=())  # missing both
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    assert len(results) == 2
    ids = {r.id for r in results}
    assert ids == {"policycodex.E002"}
    msgs = " ".join(r.msg for r in results)
    assert "classifications" in msgs
    assert "retention-schedule" in msgs


def test_duplicate_capability_provider_returns_error():
    """Two foundational policies both providing the same capability is an Error."""
    policies = [
        _stub_logical_policy(slug="retention-a", provides=("classifications", "retention-schedule")),
        _stub_logical_policy(slug="retention-b", provides=("classifications", "retention-schedule")),
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    # Both required capabilities now have 2 providers each: 2 E003 errors.
    from django.core.checks import Error
    assert len(results) == 2
    for r in results:
        assert isinstance(r, Error)
        assert r.id == "policycodex.E003"
    msgs = " ".join(r.msg for r in results)
    assert "retention-a" in msgs and "retention-b" in msgs


def test_non_foundational_policies_are_ignored_for_capability_count():
    """A policy with foundational=False does not satisfy a required capability."""
    policies = [
        _stub_logical_policy(foundational=False, provides=("classifications", "retention-schedule")),
    ]
    results = _run_check_with_mocked_reader(policies=policies)
    # Both required capabilities go unprovided.
    assert len(results) == 2
    assert all(r.id == "policycodex.E002" for r in results)
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py::test_happy_path_returns_no_errors -v 2>&1 | tail -8
```

Expected: AttributeError or similar (the check stub returns `[]` so happy-path passes vacuously, but the others fail because the stub doesn't implement the logic). Either way, several tests fail.

Run the whole new batch:

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -15
```

Expected: 4 passing (Task 2-3) + 1 passing (happy-path, vacuous) + 4 failing (missing/duplicate/non-foundational cases).

- [ ] **Step 3: Implement the capability-validation logic**

Replace the stub in `app/working_copy/checks.py` with the full happy-path-plus-capability logic. Open the file and update the function body:

```python
"""Foundational-policy startup self-check (APP-21).

Validates that every required `provides:` capability is satisfied by
exactly one published foundational policy in the local working copy.

Failure severity is gated by the POLICYCODEX_ONBOARDING_COMPLETE setting:
- False (default): missing working copy or unset repo URL returns Warning,
  letting `manage.py runserver` start during the seven-screen onboarding
  wizard. Bundle-validity failures (broken data.yaml, missing or duplicate
  capability provider) are always Error.
- True: all failures are Error and the app refuses to serve.
"""
from __future__ import annotations

from typing import Sequence

from django.conf import settings
from django.core.checks import Error, Warning, register

from app.working_copy.config import load_working_copy_config
from ingest.policy_reader import BundleAwarePolicyReader, BundleError


REQUIRED_CAPABILITIES: tuple[str, ...] = ("classifications", "retention-schedule")


@register()
def foundational_policy_check(app_configs, **kwargs) -> Sequence:
    """Return a list of Error/Warning objects; empty list means pass."""
    onboarding_complete = bool(getattr(settings, "POLICYCODEX_ONBOARDING_COMPLETE", False))

    # Resolve the policies directory. Failures here are infrastructure-level
    # (env var unset, working copy not cloned yet); Task 5 layers in the
    # onboarding-gated Warning/Error logic for these paths.
    try:
        config = load_working_copy_config()
    except RuntimeError:
        # Task 5 will refine this. For now treat as no-op (no errors); the
        # tests in Task 4 always pass POLICYCODEX_POLICY_REPO_URL so this
        # branch is unreachable from them.
        return []

    policies_dir = config.working_dir / "policies"
    if not policies_dir.exists():
        # Same Task 5 caveat as above.
        return []

    # Bundle-validity failures (broken YAML, missing files) propagate as
    # Error regardless of onboarding state.
    try:
        policies = list(BundleAwarePolicyReader(policies_dir).read())
    except BundleError as exc:
        return [Error(
            f"Broken foundational-policy bundle: {exc}",
            hint="Fix the offending file in the diocese's policy repo and re-sync via `python manage.py pull_working_copy`.",
            id="policycodex.E001",
        )]

    # Capability validation: every required capability must be provided by
    # exactly one foundational policy.
    errors = []
    for capability in REQUIRED_CAPABILITIES:
        providers = [p for p in policies if p.foundational and capability in p.provides]
        if len(providers) == 0:
            errors.append(Error(
                f"No foundational policy provides the `{capability}` capability.",
                hint=(
                    f"Add a policy bundle whose policy.md declares `foundational: true` "
                    f"and `provides: [{capability}, ...]`. See "
                    "internal/PolicyWonk-Foundational-Policy-Design.md."
                ),
                id="policycodex.E002",
            ))
        elif len(providers) > 1:
            paths = ", ".join(str(p.policy_path) for p in providers)
            errors.append(Error(
                f"Multiple foundational policies provide the `{capability}` capability: {paths}",
                hint=(
                    f"Only one policy should declare `provides: [{capability}]`. "
                    "Remove the duplicate or merge."
                ),
                id="policycodex.E003",
            ))

    return errors
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -15
```

Expected: 9 passing (the 4 from Tasks 2-3 plus the 5 new in Task 4).

- [ ] **Step 5: Commit**

```bash
git add app/working_copy/checks.py app/working_copy/tests/test_checks.py
git commit -m "feat(APP-21): capability validation (happy path, missing, duplicate)"
```

---

## Task 5: Broken-bundle handling (TDD)

**Files:**
- Modify: `app/working_copy/tests/test_checks.py`

The implementation already handles `BundleError` (added in Task 4). This task adds explicit test coverage.

- [ ] **Step 1: Write the failing test**

Append to `app/working_copy/tests/test_checks.py`:

```python
def test_broken_bundle_returns_error_with_file_hint():
    """If BundleAwarePolicyReader raises BundleError, the check returns Error E001."""
    from ingest.policy_reader import BundleError
    from django.core.checks import Error
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.side_effect = BundleError(
                    "bundle data.yaml is not valid YAML: /tmp/policies/retention/data.yaml: "
                    "expected <block end>, but found '['"
                )
                results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    err = results[0]
    assert isinstance(err, Error)
    assert err.id == "policycodex.E001"
    assert "Broken foundational-policy bundle" in err.msg
    assert "data.yaml" in err.msg  # the wrapped BundleError message
    assert "pull_working_copy" in err.hint


def test_broken_bundle_is_error_even_during_onboarding():
    """Onboarding mode does NOT downgrade bundle-validity errors. Broken bundles
    are always Error because they signal real policy-repo brokenness, not a
    not-yet-setup state."""
    from ingest.policy_reader import BundleError
    from django.core.checks import Error
    from app.working_copy import checks as checks_module

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,  # onboarding mode
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=True):
            with patch("app.working_copy.checks.BundleAwarePolicyReader") as MockReader:
                MockReader.return_value.read.side_effect = BundleError("oops")
                results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E001"
```

- [ ] **Step 2: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -15
```

Expected: 11 passing. (Both new tests pass against Task 4's already-implemented BundleError handler.)

- [ ] **Step 3: Commit**

```bash
git add app/working_copy/tests/test_checks.py
git commit -m "test(APP-21): cover broken-bundle BundleError handling (E001)"
```

---

## Task 6: Onboarding-gated infrastructure failures (TDD)

**Files:**
- Modify: `app/working_copy/checks.py`
- Modify: `app/working_copy/tests/test_checks.py`

Replace the two TODO-shaped early-returns in `foundational_policy_check` (the `except RuntimeError` and the `if not policies_dir.exists()` branches) with real onboarding-gated Warning/Error logic.

- [ ] **Step 1: Write the failing tests**

Append to `app/working_copy/tests/test_checks.py`:

```python
# Onboarding-gated infrastructure failures: missing env var, missing policies dir.

def test_unset_repo_url_during_onboarding_returns_warning():
    """POLICYCODEX_ONBOARDING_COMPLETE=False + unset repo URL → Warning."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Warning

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Warning)
    assert results[0].id == "policycodex.W001"
    assert "POLICYCODEX_POLICY_REPO_URL" in results[0].msg
    assert "onboarding" in results[0].hint.lower()


def test_unset_repo_url_post_onboarding_returns_error():
    """POLICYCODEX_ONBOARDING_COMPLETE=True + unset repo URL → Error."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Error

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="",
    ):
        results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E004"


def test_missing_policies_dir_during_onboarding_returns_warning():
    """POLICYCODEX_ONBOARDING_COMPLETE=False + policies dir missing → Warning."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Warning

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=False,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=False):
            results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Warning)
    assert results[0].id == "policycodex.W002"
    assert "pull_working_copy" in results[0].hint


def test_missing_policies_dir_post_onboarding_returns_error():
    """POLICYCODEX_ONBOARDING_COMPLETE=True + policies dir missing → Error."""
    from app.working_copy import checks as checks_module
    from django.core.checks import Error

    with override_settings(
        POLICYCODEX_ONBOARDING_COMPLETE=True,
        POLICYCODEX_POLICY_REPO_URL="https://example.com/x.git",
        POLICYCODEX_WORKING_COPY_ROOT="/tmp",
    ):
        with patch("app.working_copy.checks.Path.exists", return_value=False):
            results = checks_module.foundational_policy_check(app_configs=None)

    assert len(results) == 1
    assert isinstance(results[0], Error)
    assert results[0].id == "policycodex.E005"
```

- [ ] **Step 2: Run to confirm failure**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -15
```

Expected: 11 passing + 4 failing (the new onboarding tests; current code returns `[]` for both infrastructure-failure branches).

- [ ] **Step 3: Replace the TODO-shaped branches with real logic**

Edit `app/working_copy/checks.py`. Replace the `try / except RuntimeError` block and the `if not policies_dir.exists()` block with onboarding-gated returns:

```python
    # Resolve the working copy config. Unset POLICYCODEX_POLICY_REPO_URL is
    # an infrastructure-level failure: Warning during onboarding, Error after.
    try:
        config = load_working_copy_config()
    except RuntimeError as exc:
        if onboarding_complete:
            return [Error(
                f"Working copy not configured: {exc}",
                hint="Set POLICYCODEX_POLICY_REPO_URL to the diocese's policy repo URL.",
                id="policycodex.E004",
            )]
        return [Warning(
            f"Working copy not yet configured: {exc}",
            hint="Complete the onboarding wizard to set POLICYCODEX_POLICY_REPO_URL.",
            id="policycodex.W001",
        )]

    policies_dir = config.working_dir / "policies"
    if not policies_dir.exists():
        if onboarding_complete:
            return [Error(
                f"Policies directory not found: {policies_dir}",
                hint="Run `python manage.py pull_working_copy` to sync the diocese's policy repo.",
                id="policycodex.E005",
            )]
        return [Warning(
            f"Policies directory not yet present: {policies_dir}",
            hint="The onboarding wizard will run `pull_working_copy` to create it.",
            id="policycodex.W002",
        )]
```

- [ ] **Step 4: Run to confirm pass**

```bash
/Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest app/working_copy/tests/test_checks.py -v 2>&1 | tail -10
```

Expected: 15 passing.

- [ ] **Step 5: Full repo test suite**

```bash
cd /Users/chuck/PolicyWonk && /Users/chuck/PolicyWonk/spike/venv/bin/python -m pytest -q 2>&1 | tail -3
```

Expected: `171 passed` (156 baseline + 15 new). Capture the number.

- [ ] **Step 6: Commit**

```bash
git add app/working_copy/checks.py app/working_copy/tests/test_checks.py
git commit -m "feat(APP-21): onboarding-gated Warning/Error for infrastructure failures"
```

---

## Task 7: Manual smoke + handoff

**Files:**
- None modified.

- [ ] **Step 1: Smoke `manage.py check` against the real PT bundle (optional)**

If the local working copy is set up (i.e., the test machine has run `pull_working_copy` against PT):

```bash
cd /Users/chuck/PolicyWonk
export POLICYCODEX_POLICY_REPO_URL="https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy.git"
export POLICYCODEX_POLICY_BRANCH=main
export POLICYCODEX_WORKING_COPY_ROOT=/tmp/app21-smoke
export POLICYCODEX_ONBOARDING_COMPLETE=true
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py pull_working_copy
/Users/chuck/PolicyWonk/spike/venv/bin/python manage.py check
echo "exit=$?"
```

Expected: `System check identified no issues (0 silenced).` and exit 0, because the PT `document-retention` bundle provides both `classifications` and `retention-schedule`.

If you do not have GitHub App credentials available locally, SKIP this step and note the skip in the self-report.

- [ ] **Step 2: Smoke an intentional break (optional)**

After Step 1 succeeds, temporarily corrupt the PT bundle's `data.yaml` in `/tmp/app21-smoke/pt-policy/policies/document-retention/data.yaml` (replace the file's contents with `not: [valid: yaml`) then re-run `manage.py check`. Expect exit 1 and an Error message with the file path. Then restore the original file (or re-pull) to leave the smoke env clean.

If Step 1 was skipped, skip this step too.

- [ ] **Step 3: Confirm clean branch**

```bash
git status
git log --oneline main..HEAD
```

Expected: clean working tree; 5 commits since BASE `f6a65d3`:

1. `feat(APP-21): WorkingCopyAppConfig + ONBOARDING_COMPLETE setting + INSTALLED_APPS wire-up`
2. `feat(APP-21): foundational_policy_check stub + Django registration`
3. `feat(APP-21): capability validation (happy path, missing, duplicate)`
4. `test(APP-21): cover broken-bundle BundleError handling (E001)`
5. `feat(APP-21): onboarding-gated Warning/Error for infrastructure failures`

If counts differ, surface in the self-report.

- [ ] **Step 4: Compose self-report**

Cover:
- Goal in one sentence.
- Branch name (`worktree-agent-<id>`) and final commit SHA.
- Files created / modified.
- Commit list with messages.
- Test count before / after (expect 156 → 171).
- Smoke result (Step 1-2): PASS / SKIPPED / FAIL with notes.
- Any deviations from the plan + rationale.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT.

- [ ] **Step 5: Handoff**

Do not merge to main. Do not push. The dispatching session (Scarlet) will route the branch through spec-compliance review and code-quality review per `superpowers:subagent-driven-development`.

---

## Definition of Done

- `app/working_copy/apps.py` exists with `WorkingCopyAppConfig(AppConfig)` (NOT `WorkingCopyConfig`).
- `app/working_copy/checks.py` exists with `foundational_policy_check` registered via `@register()`.
- `policycodex_site/settings.py` has `'app.working_copy.apps.WorkingCopyAppConfig'` in `INSTALLED_APPS` and `POLICYCODEX_ONBOARDING_COMPLETE` driven from env var with a truthy parser (accepts `"1"`, `"true"`, `"yes"` case-insensitive; rejects `"0"`, `"false"`, `"no"`, empty).
- `app/working_copy/tests/test_checks.py` has 15 tests covering: 2 AppConfig wiring tests, 2 registration tests, 5 capability-validation tests (happy + missing + duplicate + non-foundational + two-missing), 2 broken-bundle tests, 4 onboarding-gated infrastructure tests.
- All 5 error/warning ids used (E001 broken bundle, E002 missing capability, E003 duplicate capability, E004 post-onboarding unset URL, E005 post-onboarding missing dir, W001 onboarding unset URL, W002 onboarding missing dir).
- Bundle-validity errors (E001/E002/E003) are ALWAYS Error regardless of onboarding state.
- Infrastructure failures (unset URL, missing dir) are Warning during onboarding, Error after.
- Full repo test suite: 156 → 171 passing.
- `manage.py check` exits 0 against a valid bundle.
- 5 commits on the branch since BASE `f6a65d3`, all with `APP-21` in the message.
- No edits outside the 4 files in **File Structure**.
- No em dashes anywhere in new content.
- No PT-specific tokens (`pt`, `PT`, `pensacola`, `tallahassee`) anywhere in `app/working_copy/checks.py`, `app/working_copy/apps.py`, the test file, or settings.py changes. PT names appear ONLY in the optional smoke env exports in Task 7.

---

## Self-Review

**Spec coverage:**
- Ticket says "validate every `provides:` capability the app needs (`classifications`, `retention-schedule`) is satisfied by exactly one published foundational policy" → Task 4 ✓
- Ticket says "On miss or invalid data.yaml, refuse to serve and show a clear error pointing at the broken file" → Tasks 4 (E002 with path-pointing hint), 5 (E001 wrapping BundleError) ✓
- Foundational-policy design says L3 protection layer → Task 3 registers via Django check framework, which produces `Error` that makes `manage.py check` exit non-zero ✓
- Onboarding-gated severity (Chuck's decision) → Task 6 ✓
- Required capabilities hardcoded per design line 151 → Task 3 sets `REQUIRED_CAPABILITIES` ✓
- "Exactly one" provider rule (not just "at least one") → Task 4's duplicate-detection (E003) ✓

**Placeholder scan:** No TBDs, no "TODO", no "implement later". Every step has code. Every test has assertions. Every error has `id`, `msg`, `hint`.

**Type consistency:**
- `LogicalPolicy.provides: tuple[str, ...]` — used consistently in `_stub_logical_policy` (default `("classifications", "retention-schedule")`) and the check function (`capability in p.provides`).
- `REQUIRED_CAPABILITIES: tuple[str, ...]` — same shape.
- Check function signature `(app_configs, **kwargs) -> Sequence` — used identically across Tasks 3, 4, 6.
- Error ids in tests match ids in implementation: E001, E002, E003, E004, E005, W001, W002 — all consistent across plan.
- `WorkingCopyAppConfig` class name used consistently across Task 2's apps.py creation, the test assertion, and settings.py `INSTALLED_APPS`.

No issues found.
