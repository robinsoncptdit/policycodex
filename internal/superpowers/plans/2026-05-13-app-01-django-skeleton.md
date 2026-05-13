# APP-01 Django Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable Django project at the repo root so APP-02 (local auth + identity-to-Git-author) and the catalog/wizard tickets have a real app to hang views off of.

**Architecture:** A single Django 5.x project named `policycodex_site` at the repo root, with SQLite as the default DB and one stub Django app named `core` for a smoke health view. Existing `ai/`, `app/`, and `spike/` packages are untouched; the Django settings file adds `BASE_DIR.parent` to `sys.path`-equivalent (via `INSTALLED_APPS` referencing `app.git_provider` as needed by future tickets, not now). `pytest-django` is the test runner so we stay on pytest project-wide. No custom apps yet beyond `core`; APP-02+ add real apps as they land.

**Tech Stack:** Python 3.12, Django >=5.0, pytest, pytest-django >=4.8, SQLite (stdlib).

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` APP-01 ("Web framework choice and project skeleton"). Framework decided 2026-05-11: Python + Django (`internal/PolicyWonk-Framework-Evaluation.md`).

---

## File Structure

- Create: `manage.py` — Django entry point at repo root.
- Create: `policycodex_site/__init__.py` — Django project package.
- Create: `policycodex_site/settings.py` — settings (SQLite, English/UTC, minimal middleware, `core` in INSTALLED_APPS).
- Create: `policycodex_site/urls.py` — root URLconf, includes `core.urls`.
- Create: `policycodex_site/wsgi.py` — WSGI entry.
- Create: `policycodex_site/asgi.py` — ASGI entry.
- Create: `core/__init__.py` — stub Django app.
- Create: `core/apps.py` — AppConfig.
- Create: `core/urls.py` — `health/` route only.
- Create: `core/views.py` — health view returning JSON `{"status": "ok"}`.
- Create: `core/tests.py` — health view test using pytest-django client.
- Create: `pytest.ini` — wire pytest-django and `DJANGO_SETTINGS_MODULE`.
- Modify: `app/requirements.txt` — add `django>=5.0` and `pytest-django>=4.8`.
- Modify: `.gitignore` — add `db.sqlite3`, `*.sqlite3`, `staticfiles/`.

**Naming note:** the Django project is `policycodex_site` (not `policycodex`) so the package name doesn't collide with any future top-level `policycodex/` Python package or with the public product name. Public-facing strings use "PolicyCodex"; only the import path uses `policycodex_site`.

---

## Task 1: Add Django + pytest-django to requirements

**Files:**
- Modify: `app/requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Update `app/requirements.txt`**

Replace contents with:

```
django>=5.0
pytest>=7.4
pytest-django>=4.8
```

- [ ] **Step 2: Update `.gitignore`**

Append:

```
db.sqlite3
*.sqlite3
staticfiles/
```

- [ ] **Step 3: Install into the existing venv**

```bash
source ai/venv/bin/activate && pip install -r app/requirements.txt
```

Expected: Django and pytest-django installed; no errors.

- [ ] **Step 4: Commit**

```bash
git add app/requirements.txt .gitignore
git commit -m "chore(APP-01): add Django + pytest-django to app requirements"
```

---

## Task 2: Generate the Django project skeleton

**Files:**
- Create: `manage.py`, `policycodex_site/{__init__.py,settings.py,urls.py,wsgi.py,asgi.py}`

- [ ] **Step 1: Generate the project**

```bash
cd /Users/chuck/PolicyWonk && django-admin startproject policycodex_site .
```

Expected: creates `manage.py` and `policycodex_site/` at repo root.

- [ ] **Step 2: Edit `policycodex_site/settings.py`**

Make these minimal changes from the default:

1. `DEBUG = True` (development default; APP-02+ will plumb env-var-based config).
2. `ALLOWED_HOSTS = ["localhost", "127.0.0.1"]`.
3. `TIME_ZONE = "America/Los_Angeles"` (Chuck's tz).
4. Leave SQLite as the default `DATABASES["default"]`.

Do not change `SECRET_KEY` yet — APP-02 plumbs it from env. Note: the generated `SECRET_KEY` will be committed for dev only; APP-02 must rotate it via env var before any non-local deploy.

- [ ] **Step 3: Run the Django check**

```bash
cd /Users/chuck/PolicyWonk && python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Apply initial migrations to verify the DB layer works**

```bash
cd /Users/chuck/PolicyWonk && python manage.py migrate
```

Expected: applies admin/auth/contenttypes/sessions migrations; creates `db.sqlite3`.

- [ ] **Step 5: Commit (excluding the SQLite file, which is gitignored)**

```bash
git add manage.py policycodex_site/
git commit -m "feat(APP-01): generate Django 5 project skeleton (policycodex_site)"
```

---

## Task 3: Add a `core` Django app with a `/health/` view

**Files:**
- Create: `core/{__init__.py,apps.py,urls.py,views.py,tests.py}`
- Modify: `policycodex_site/settings.py` (INSTALLED_APPS), `policycodex_site/urls.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests.py`:

```python
"""Smoke tests for the core app."""
import pytest


@pytest.mark.django_db
def test_health_returns_ok(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Create `pytest.ini` at repo root**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = policycodex_site.settings
python_files = tests.py test_*.py *_test.py
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest core/tests.py -v
```

Expected: FAIL (no `core` app, 404 on `/health/`).

- [ ] **Step 4: Create the `core` app**

`core/__init__.py`: empty file.

`core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
```

`core/views.py`:

```python
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})
```

`core/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
]
```

In `policycodex_site/settings.py`, add `"core"` to `INSTALLED_APPS`.

In `policycodex_site/urls.py`, add the include and import:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest core/tests.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Smoke-test the dev server manually**

```bash
cd /Users/chuck/PolicyWonk && python manage.py runserver 0:8000 &
sleep 2 && curl -s http://localhost:8000/health/ ; echo
kill %1 2>/dev/null
```

Expected: `{"status": "ok"}` printed.

- [ ] **Step 7: Commit**

```bash
git add core/ pytest.ini policycodex_site/settings.py policycodex_site/urls.py
git commit -m "feat(APP-01): add core app with /health/ view + pytest-django wiring"
```

---

## Task 4: Verify existing test suites still pass under the new pytest config

**Files:** (none modified; validation only)

- [ ] **Step 1: Run the full test suite from the repo root**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest -v
```

Expected: `core/tests.py::test_health_returns_ok` passes. If existing `ai/tests/test_provider.py` or `app/git_provider/tests/test_base.py` fail because pytest collection now goes through `policycodex_site.settings`, narrow `python_files` in `pytest.ini` or add a per-package `conftest.py`. **Do not edit those pre-existing test files** — adjust `pytest.ini` or add conftest stubs that scope the Django settings to `core/`.

If failures occur, document the fix in this task before continuing. If everything passes, no action.

- [ ] **Step 2: If a fix was applied, commit it**

```bash
git add pytest.ini  # or whichever conftest.py was added
git commit -m "fix(APP-01): scope pytest-django config so existing test suites still run"
```

If no fix needed, skip.

---

## Definition of Done

- `python manage.py check` → "no issues".
- `python manage.py migrate` → applies migrations cleanly to a fresh SQLite DB.
- `python manage.py runserver` → serves; `curl http://localhost:8000/health/` returns `{"status": "ok"}`.
- `python -m pytest` from repo root → existing `ai/`, `app/`, `spike/` tests still pass, plus `core/tests.py::test_health_returns_ok`.
- New files committed; `db.sqlite3` not committed.
- No changes to `ai/`, `spike/`, or `app/git_provider/` source code (only `app/requirements.txt`).
