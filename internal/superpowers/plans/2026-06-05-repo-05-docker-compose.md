# REPO-05 Docker Compose + One-Command Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship PolicyCodex as a containerized, one-command install: a PT-free Docker image, a build-from-source Compose file (Profile A, the working DISC path) and a published-image Compose stub (Profile B), with per-diocese config entering via mounted volumes, Django production-safe settings, and the AGPL "View Source" footer.

**Architecture:** Django stays the same app; we make the deploy-time knobs (SECRET_KEY, DEBUG, ALLOWED_HOSTS, DB path, source URL) env-driven through a small pure helper module so they are unit-testable without reloading Django. The container runs gunicorn behind WhiteNoise (so static assets serve with DEBUG off). State (SQLite DB, working copies) lives in a mounted named volume; credentials (`config.env` + the GitHub App `.pem`) are bind-mounted read-only from the host's existing `~/.config/policycodex/`, so secrets never enter the image or any Compose file. Profile B references a not-yet-published registry image and is validated only by `docker compose config` (registry publishing is post-DISC).

**Tech Stack:** Python 3.12 (`python:3.12-slim-bookworm` base; REPO-11 ratifies the pin), Django 6.0, gunicorn, WhiteNoise, Docker + Docker Compose v2, pytest/pytest-django.

---

## Context an implementer must know

Read these before starting. Do NOT re-derive; the facts are below.

- **Config is already env-driven.** `policycodex_site/settings.py` reads `POLICYCODEX_POLICY_REPO_URL`, `POLICYCODEX_POLICY_BRANCH`, `POLICYCODEX_WORKING_COPY_ROOT`, `POLICYCODEX_ONBOARDING_COMPLETE` from `os.environ` (lines 21-33). Follow that pattern.
- **Working-copy default:** `app/working_copy/config.py:36` falls back to `Path.home() / ".policycodex" / "working-copies"` when `POLICYCODEX_WORKING_COPY_ROOT` is empty. In the container we set that env var to a volume path, so no code change there.
- **Credentials loader already supports an env override.** `app/git_provider/github_config.py:48` uses `POLICYCODEX_CONFIG_PATH` if set, else `~/.config/policycodex/config.env`. The container sets `POLICYCODEX_CONFIG_PATH` to the mounted path. The `config.env` value `POLICYCODEX_GH_PRIVATE_KEY_PATH` must be written by the operator as a *container-visible* path (documented in `.env.example`). No code change.
- **DB** is `policycodex_site/settings.py:98` → `BASE_DIR / 'db.sqlite3'`. We make this env-driven for volume persistence.
- **SECRET_KEY** is a hardcoded `django-insecure-...` literal at `settings.py:40`, with a TODO at `settings.py:37` explicitly assigning rotation to REPO-05. `DEBUG = True` (line 43), `ALLOWED_HOSTS = ['localhost','127.0.0.1']` (line 45).
- **No static handling for DEBUG off.** `STATIC_URL = 'static/'` is set (settings.py) but there is no `STATIC_ROOT` and no WhiteNoise. With DEBUG off Django will not serve admin/login CSS. We add WhiteNoise.
- **The app shells out to `git`** (`app/git_provider/github_provider.py` runs `git clone/push/pull`). The image MUST install `git`.
- **AGPL footer** goes in `core/templates/base.html:31-33` (the `<footer>` block).
- **Generic-ship guard:** `tests/test_generic_ship.py` scans six shipping roots for PT/internal leakage but does NOT scan root-level files. New root-level shipping files (Dockerfile, compose, install.sh, .env.example, entrypoint) must be added to its scan.
- **Test interpreter:** run the suite with `ai/venv/bin/python -m pytest` from the repo root. There is no root venv.
- **pip pins:** use `>=` floor constraints in `requirements.txt`, never exact `==` pins.
- **Trunk-based:** commit each task straight to `main`.
- **The decided design forks (already approved):** (1) hardening IS in scope; (2) Profile B is a documented stub validated by `docker compose config`; (3) secrets via read-only bind mount of `~/.config/policycodex/`; (4) footer URL is a configurable setting with a placeholder default.

## File Structure

**Create:**
- `policycodex_site/env.py` — pure helpers that turn `os.environ` into settings values (secret key, debug, hosts, db path, source url). Unit-testable with dict inputs.
- `core/context_processors.py` — exposes `source_url` to all templates.
- `Dockerfile` — build-from-source image; installs git; collectstatic at build; gunicorn entrypoint.
- `.dockerignore` — keep venvs, .git, archive, internal, spike outputs, db out of the build context.
- `docker/entrypoint.sh` — migrate, optional createsuperuser, exec gunicorn.
- `docker-compose.yml` — Profile A (build from source). The working DISC path; default file.
- `docker-compose.pull.yml` — Profile B (pull published image). Documented stub.
- `.env.example` — documents every env var the container reads.
- `install.sh` — one-command: verify docker, seed `.env`, `docker compose up --build`.
- `tests/test_settings_env.py` — unit tests for `policycodex_site/env.py`.
- `tests/test_docker_packaging.py` — structural tests for Dockerfile/compose/.env.example/install.sh (no docker daemon needed).
- `core/tests/test_source_footer.py` — renders a page, asserts the View Source link.

**Modify:**
- `policycodex_site/settings.py` — call the new helpers; add `POLICYCODEX_SOURCE_URL`; add WhiteNoise middleware + `STATICFILES` storage + `STATIC_ROOT`; register the context processor.
- `app/requirements.txt` — add `gunicorn>=21.0`, `whitenoise>=6.0`.
- `core/templates/base.html` — footer "View Source" link.
- `tests/test_generic_ship.py` — extend scan to root-level shipping files.
- `README.md` — replace the "planned" docker note with the real Quick Start (Profile A) + secrets/volume notes.

---

### Task 1: Env-driven settings helpers + hardening

**Files:**
- Create: `policycodex_site/env.py`
- Create: `tests/test_settings_env.py`
- Modify: `policycodex_site/settings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings_env.py`:

```python
"""Unit tests for policycodex_site.env (REPO-05 deploy-time settings helpers)."""
from pathlib import Path

import pytest

from policycodex_site import env

_DEV_DEFAULT = "django-insecure-77@z8v71u2tc7%7qp)rpg7!cctxh32l5+_**y%4uw9+j(9f(&w"


def test_secret_key_uses_env_when_set():
    assert env.get_secret_key({"DJANGO_SECRET_KEY": "abc"}, debug=False) == "abc"


def test_secret_key_falls_back_to_dev_default_in_debug():
    assert env.get_secret_key({}, debug=True) == _DEV_DEFAULT


def test_secret_key_required_when_not_debug():
    with pytest.raises(env.SettingsError):
        env.get_secret_key({}, debug=False)


def test_debug_defaults_off():
    assert env.get_debug({}) is False


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "Yes"])
def test_debug_truthy(raw):
    assert env.get_debug({"DJANGO_DEBUG": raw}) is True


@pytest.mark.parametrize("raw", ["0", "false", "no", ""])
def test_debug_falsy(raw):
    assert env.get_debug({"DJANGO_DEBUG": raw}) is False


def test_allowed_hosts_default_is_localhost():
    assert env.get_allowed_hosts({}) == ["localhost", "127.0.0.1"]


def test_allowed_hosts_parses_csv_and_strips():
    assert env.get_allowed_hosts(
        {"DJANGO_ALLOWED_HOSTS": "example.org, 10.0.0.5 ,localhost"}
    ) == ["example.org", "10.0.0.5", "localhost"]


def test_db_path_default_is_base_dir(tmp_path):
    assert env.get_db_path({}, tmp_path) == tmp_path / "db.sqlite3"


def test_db_path_uses_env(tmp_path):
    assert env.get_db_path({"POLICYCODEX_DB_PATH": "/data/x.sqlite3"}, tmp_path) == Path(
        "/data/x.sqlite3"
    )


def test_source_url_default_placeholder():
    assert env.get_source_url({}) == "https://github.com/policycodex/policycodex"


def test_source_url_uses_env():
    assert env.get_source_url({"POLICYCODEX_SOURCE_URL": "https://x.test/repo"}) == (
        "https://x.test/repo"
    )
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `ai/venv/bin/python -m pytest tests/test_settings_env.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'policycodex_site.env'`.

- [ ] **Step 3: Write the helper module**

Create `policycodex_site/env.py`:

```python
"""Deploy-time settings helpers (REPO-05).

Pure functions that translate an environment mapping into Django setting
values. Kept separate from settings.py so they are unit-testable without
reloading Django. settings.py calls these with os.environ.
"""
from __future__ import annotations

from pathlib import Path

# The historical insecure dev key. Used only when DEBUG is on and no
# DJANGO_SECRET_KEY is supplied, so `manage.py runserver` keeps working
# locally with zero config. Never used when DEBUG is off.
_DEV_SECRET_KEY = "django-insecure-77@z8v71u2tc7%7qp)rpg7!cctxh32l5+_**y%4uw9+j(9f(&w"

_TRUTHY = ("1", "true", "yes")

_DEFAULT_SOURCE_URL = "https://github.com/policycodex/policycodex"


class SettingsError(Exception):
    """Raised when a required deploy-time setting is missing."""


def get_debug(environ) -> bool:
    return environ.get("DJANGO_DEBUG", "").strip().lower() in _TRUTHY


def get_secret_key(environ, debug: bool) -> str:
    key = environ.get("DJANGO_SECRET_KEY", "").strip()
    if key:
        return key
    if debug:
        return _DEV_SECRET_KEY
    raise SettingsError(
        "DJANGO_SECRET_KEY must be set when DEBUG is off. Generate one and "
        "pass it via the environment (see .env.example)."
    )


def get_allowed_hosts(environ) -> list[str]:
    raw = environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
    if not raw:
        return ["localhost", "127.0.0.1"]
    return [h.strip() for h in raw.split(",") if h.strip()]


def get_db_path(environ, base_dir: Path) -> Path:
    raw = environ.get("POLICYCODEX_DB_PATH", "").strip()
    return Path(raw) if raw else base_dir / "db.sqlite3"


def get_source_url(environ) -> str:
    return environ.get("POLICYCODEX_SOURCE_URL", "").strip() or _DEFAULT_SOURCE_URL
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `ai/venv/bin/python -m pytest tests/test_settings_env.py -v`
Expected: PASS (all cases).

- [ ] **Step 5: Wire the helpers into settings.py**

In `policycodex_site/settings.py`:

Add the import near the top (after `from pathlib import Path`):

```python
from policycodex_site import env as _env
```

Replace the SECRET_KEY / DEBUG / ALLOWED_HOSTS block (currently lines ~36-45, the `# Quick-start` comment through `ALLOWED_HOSTS = [...]`) with:

```python
# Deploy-time knobs (REPO-05). Driven by the environment so the same image
# runs safely in production. Locally, `manage.py runserver` with no env set
# gets DEBUG on and the historical dev key (see policycodex_site/env.py).
DEBUG = _env.get_debug(os.environ)

# SECURITY: when DEBUG is off, DJANGO_SECRET_KEY is required.
SECRET_KEY = _env.get_secret_key(os.environ, debug=DEBUG)

ALLOWED_HOSTS = _env.get_allowed_hosts(os.environ)
```

Replace the DATABASES block (lines ~95-100) with:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _env.get_db_path(os.environ, BASE_DIR),
    }
}
```

Add, in the section with the other `POLICYCODEX_*` settings (after line ~23):

```python
# AGPL "View Source" footer target (REPO-05). Placeholder org until the
# public GitHub org slug is finalized; override via POLICYCODEX_SOURCE_URL.
POLICYCODEX_SOURCE_URL = _env.get_source_url(os.environ)
```

- [ ] **Step 6: Run the full suite to confirm nothing regressed**

Run: `ai/venv/bin/python -m pytest`
Expected: PASS. Note: DEBUG now defaults to False under pytest; the Django test client does not need static serving, so the suite stays green. (WhiteNoise lands in Task 2.)

- [ ] **Step 7: Commit**

```bash
git add policycodex_site/env.py tests/test_settings_env.py policycodex_site/settings.py
git commit -m "feat(REPO-05): env-drive SECRET_KEY/DEBUG/ALLOWED_HOSTS/DB path + source URL"
```

---

### Task 2: WhiteNoise static serving (so DEBUG-off works)

**Files:**
- Modify: `app/requirements.txt`
- Modify: `policycodex_site/settings.py`

- [ ] **Step 1: Add the dependencies**

In `app/requirements.txt`, add these two lines (keep `>=` floors per project convention):

```
gunicorn>=21.0
whitenoise>=6.0
```

- [ ] **Step 2: Install into the test venv**

Run: `ai/venv/bin/pip install "whitenoise>=6.0" "gunicorn>=21.0"`
Expected: both install successfully.

- [ ] **Step 3: Add WhiteNoise middleware + static storage in settings.py**

In `policycodex_site/settings.py`, in `MIDDLEWARE`, insert WhiteNoise immediately after `SecurityMiddleware`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

Replace the `STATIC_URL = 'static/'` line with:

```python
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

- [ ] **Step 4: Verify collectstatic runs and the suite passes**

Run: `ai/venv/bin/python manage.py collectstatic --noinput`
Expected: succeeds, writes to `staticfiles/` (already gitignored).

Run: `ai/venv/bin/python -m pytest`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/requirements.txt policycodex_site/settings.py
git commit -m "feat(REPO-05): serve static via WhiteNoise so DEBUG-off deploys work"
```

---

### Task 3: AGPL "View Source" footer

**Files:**
- Create: `core/context_processors.py`
- Create: `core/tests/test_source_footer.py`
- Modify: `policycodex_site/settings.py`
- Modify: `core/templates/base.html`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_source_footer.py`:

```python
"""The AGPL 'View Source' footer must appear on rendered pages (REPO-05)."""
import pytest
from django.test import Client


@pytest.mark.django_db
def test_login_page_shows_view_source_link(settings):
    settings.POLICYCODEX_SOURCE_URL = "https://example.test/policycodex"
    resp = Client().get("/login/", HTTP_HOST="127.0.0.1")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "View Source" in body
    assert 'href="https://example.test/policycodex"' in body
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `ai/venv/bin/python -m pytest core/tests/test_source_footer.py -v`
Expected: FAIL — "View Source" not in body.

- [ ] **Step 3: Add the context processor**

Create `core/context_processors.py`:

```python
"""Template context processors for the core app."""
from django.conf import settings


def source_url(request):
    """Expose the AGPL source-link target to every template."""
    return {"source_url": settings.POLICYCODEX_SOURCE_URL}
```

- [ ] **Step 4: Register the context processor**

In `policycodex_site/settings.py`, add it to the `TEMPLATES[0]['OPTIONS']['context_processors']` list:

```python
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.source_url',
            ],
```

- [ ] **Step 5: Update the footer**

In `core/templates/base.html`, replace the `<footer>` block (lines 31-33):

```html
    <footer>
      <small>
        PolicyCodex v0.1 &middot;
        <a href="{{ source_url }}">View Source</a> (AGPL-3.0)
      </small>
    </footer>
```

- [ ] **Step 6: Run the test, then the suite**

Run: `ai/venv/bin/python -m pytest core/tests/test_source_footer.py -v`
Expected: PASS.

Run: `ai/venv/bin/python -m pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/context_processors.py core/tests/test_source_footer.py policycodex_site/settings.py core/templates/base.html
git commit -m "feat(REPO-05): AGPL View Source footer link (configurable source URL)"
```

---

### Task 4: Dockerfile, .dockerignore, entrypoint

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker/entrypoint.sh`

- [ ] **Step 1: Write the .dockerignore**

Create `.dockerignore`:

```
.git
.gitignore
**/__pycache__/
*.pyc
**/venv/
**/.venv/
ai/venv/
spike/venv/
*.sqlite3
db.sqlite3
staticfiles/
archive/
internal/
.obsidian/
.pytest_cache/
.tmp-reviews/
.worktrees/
.claude/
spike/outputs*/
**/.DS_Store
docs/superpowers/.cache/
```

- [ ] **Step 2: Write the entrypoint**

Create `docker/entrypoint.sh`:

```bash
#!/usr/bin/env sh
set -e

# Apply migrations against the (volume-backed) database.
python manage.py migrate --noinput

# Create the admin user only when all three env vars are supplied and the
# user does not already exist. Django's createsuperuser --noinput reads
# DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD from the environment.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec gunicorn policycodex_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
```

- [ ] **Step 3: Write the Dockerfile**

Create `Dockerfile`:

```dockerfile
# PolicyCodex application image (REPO-05). Generic and diocese-agnostic:
# per-diocese config enters at runtime via env + mounted volumes, never baked in.
FROM python:3.12-slim-bookworm

# git is required: the app shells out to git clone/push/pull for the
# diocese policy repo. The rest are slim-image build basics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps first for layer caching.
COPY ai/requirements.txt ai/requirements.txt
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r ai/requirements.txt -r app/requirements.txt

# Copy the application source.
COPY . .

# Collect static assets at build time (served by WhiteNoise at runtime).
# A throwaway key satisfies settings import; DEBUG off is fine for collectstatic.
RUN DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --noinput

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

- [ ] **Step 4: Build the image to verify it succeeds**

Run: `docker build -t policycodex:dev .`
Expected: builds successfully through collectstatic and entrypoint copy. (If the controller's environment has no docker daemon, record that this step must be run manually; the structural test in Task 7 still guards the file contents.)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore docker/entrypoint.sh
git commit -m "feat(REPO-05): PT-free Dockerfile + entrypoint (gunicorn, git, collectstatic)"
```

---

### Task 5: Compose files (Profile A build, Profile B pull stub) + .env.example

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.pull.yml`
- Create: `.env.example`

- [ ] **Step 1: Write the build-from-source compose (Profile A)**

Create `docker-compose.yml`:

```yaml
# Profile A: build PolicyCodex from source. The working install path for
# developer dioceses and the DISC demo. `docker compose up --build`.
services:
  app:
    build: .
    image: policycodex:local
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      # Persistent state: SQLite DB + cloned working copies.
      - policycodex-data:/data
      # Credentials, read-only, straight from the host convention dir.
      # config.env's POLICYCODEX_GH_PRIVATE_KEY_PATH must point inside here.
      - ${HOME}/.config/policycodex:/secrets:ro
    restart: unless-stopped

volumes:
  policycodex-data:
```

- [ ] **Step 2: Write the published-image compose (Profile B stub)**

Create `docker-compose.pull.yml`:

```yaml
# Profile B: pull a pre-built published image (boxed ship for non-developer
# dioceses). The image below is NOT published yet; registry publishing is a
# post-DISC follow-up. This file is validated by `docker compose config`;
# it will run once the image is pushed. Until then, use docker-compose.yml.
services:
  app:
    image: ghcr.io/policycodex/policycodex:latest
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - policycodex-data:/data
      - ${HOME}/.config/policycodex:/secrets:ro
    restart: unless-stopped

volumes:
  policycodex-data:
```

- [ ] **Step 3: Write .env.example**

Create `.env.example`:

```bash
# PolicyCodex container configuration. Copy to .env and fill in.
# Secrets (GitHub App key, LLM API key) do NOT go here — they live in
# ~/.config/policycodex/, bind-mounted read-only at /secrets.

# --- Django deploy-time (REPO-05) ---
# Required when DJANGO_DEBUG is not set/true. Generate with:
#   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
DJANGO_SECRET_KEY=
# Leave empty/0 for production. Set to 1 for local debugging only.
DJANGO_DEBUG=
# Comma-separated hostnames this instance answers on (e.g. policycodex.example.org).
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# --- Persistent state (volume-backed) ---
POLICYCODEX_DB_PATH=/data/db.sqlite3
POLICYCODEX_WORKING_COPY_ROOT=/data/working-copies

# --- Credentials (mounted read-only at /secrets) ---
# Point the loader at the mounted config.env. Inside that file,
# POLICYCODEX_GH_PRIVATE_KEY_PATH must be a /secrets/... path.
POLICYCODEX_CONFIG_PATH=/secrets/config.env

# --- Diocese policy repo (or set via the onboarding wizard) ---
POLICYCODEX_POLICY_REPO_URL=
POLICYCODEX_POLICY_BRANCH=main
POLICYCODEX_ONBOARDING_COMPLETE=

# --- AGPL footer ---
POLICYCODEX_SOURCE_URL=https://github.com/policycodex/policycodex

# --- Initial admin user (optional; created on first start if all set) ---
DJANGO_SUPERUSER_USERNAME=
DJANGO_SUPERUSER_EMAIL=
DJANGO_SUPERUSER_PASSWORD=
```

- [ ] **Step 4: Validate both compose files parse**

Run: `docker compose -f docker-compose.yml config >/dev/null && echo OK-A`
Run: `docker compose -f docker-compose.pull.yml config >/dev/null && echo OK-B`
Expected: `OK-A` and `OK-B`. (If no docker daemon is available to the controller, record that these must be run manually; Task 7's structural test guards the file contents either way.)

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml docker-compose.pull.yml .env.example
git commit -m "feat(REPO-05): Profile A build compose + Profile B pull stub + .env.example"
```

---

### Task 6: One-command install script

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Write install.sh**

Create `install.sh`:

```bash
#!/usr/bin/env bash
# PolicyCodex one-command install (REPO-05). Builds and starts the stack
# from source (Profile A). Run from the repo root: ./install.sh
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed. Install Docker first: https://docs.docker.com/get-docker/" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Error: 'docker compose' (v2) is required." >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Edit it to set DJANGO_SECRET_KEY and your"
    echo "diocese values, then re-run ./install.sh. Secrets stay in ~/.config/policycodex/."
    exit 0
fi

echo "Building and starting PolicyCodex (this may take a few minutes the first time)..."
docker compose up --build -d

echo
echo "PolicyCodex is starting at http://localhost:8000"
echo "Complete the onboarding wizard in your browser, or run the AI inventory pass."
echo "Logs: docker compose logs -f"
```

- [ ] **Step 2: Make it executable and syntax-check it**

Run: `chmod +x install.sh && bash -n install.sh && echo SYNTAX-OK`
Expected: `SYNTAX-OK`.

- [ ] **Step 3: Verify the no-.env branch (dry run, does not start docker)**

Run: `rm -f .env && ./install.sh; ls .env && echo ENV-CREATED; rm -f .env`
Expected: prints the "Created .env" guidance, exits 0, `.env` exists (then cleaned up). (`.env` is gitignored, so this leaves the tree clean.)

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat(REPO-05): one-command install.sh (docker preflight + compose up)"
```

---

### Task 7: Guard the new shipping files (PT-free + structural)

**Files:**
- Modify: `tests/test_generic_ship.py`
- Create: `tests/test_docker_packaging.py`

- [ ] **Step 1: Write the failing structural test**

Create `tests/test_docker_packaging.py`:

```python
"""Structural guards for the REPO-05 Docker packaging (no docker daemon needed)."""
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def test_packaging_files_exist():
    for name in (
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.pull.yml",
        ".env.example",
        "install.sh",
        "docker/entrypoint.sh",
        ".dockerignore",
    ):
        assert (_ROOT / name).is_file(), f"missing {name}"


def test_dockerfile_installs_git_and_runs_gunicorn():
    text = _read("Dockerfile")
    assert "install" in text and "git" in text  # app shells out to git
    assert "collectstatic" in text


def test_entrypoint_migrates_and_execs_gunicorn():
    text = _read("docker/entrypoint.sh")
    assert "migrate" in text
    assert "gunicorn" in text


def test_build_compose_builds_and_mounts_secrets_readonly():
    text = _read("docker-compose.yml")
    assert "build:" in text
    assert "/secrets:ro" in text
    assert "policycodex-data:/data" in text


def test_pull_compose_references_registry_image():
    text = _read("docker-compose.pull.yml")
    assert "image:" in text
    assert "ghcr.io/" in text
    assert "build:" not in text  # Profile B pulls, does not build


def test_env_example_documents_required_keys():
    text = _read(".env.example")
    for key in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "POLICYCODEX_DB_PATH",
        "POLICYCODEX_CONFIG_PATH",
        "POLICYCODEX_SOURCE_URL",
    ):
        assert key in text, f"{key} not documented in .env.example"


def test_env_example_holds_no_real_secret_values():
    # Keys are present but must ship empty (no leaked credential).
    for line in _read(".env.example").splitlines():
        if line.startswith("DJANGO_SECRET_KEY="):
            assert line.strip() == "DJANGO_SECRET_KEY="
```

- [ ] **Step 2: Run it to confirm it passes (files exist from Tasks 4-6)**

Run: `ai/venv/bin/python -m pytest tests/test_docker_packaging.py -v`
Expected: PASS. (If any assert fails, fix the corresponding file from Tasks 4-6, do not weaken the test.)

- [ ] **Step 3: Extend the generic-ship guard to root-level shipping files**

In `tests/test_generic_ship.py`, add a module-level constant after `_SHIPPING_ROOTS` (line 23):

```python
# Root-level files that ship in the public repo and must stay generic.
_SHIPPING_ROOT_FILES = (
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.pull.yml",
    ".env.example",
    "install.sh",
    "docker/entrypoint.sh",
)
```

Then, in `_scanned_files()`, after the `for root in _SHIPPING_ROOTS:` loop (after the existing `yield path` block, still inside the function), add:

```python
    for rel in _SHIPPING_ROOT_FILES:
        path = _REPO_ROOT / rel
        if path.is_file():
            yield path
```

Note: these files have no/uncommon suffixes (`Dockerfile`, `.env.example`), so they bypass the `_SCANNED_SUFFIXES` filter by being yielded directly. That is intended — they are an explicit allowlist of root shipping files.

- [ ] **Step 4: Run the generic-ship guard and the full suite**

Run: `ai/venv/bin/python -m pytest tests/test_generic_ship.py tests/test_docker_packaging.py -v`
Expected: PASS — no PT/internal leakage in the new files.

Run: `ai/venv/bin/python -m pytest`
Expected: PASS (full suite).

- [ ] **Step 5: Commit**

```bash
git add tests/test_generic_ship.py tests/test_docker_packaging.py
git commit -m "test(REPO-05): structural Docker guards + extend generic-ship scan to root files"
```

---

### Task 8: README Quick Start (real docker path) + docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the deferred docker note with the real install path**

In `README.md`, the Quick Start currently ends (line ~130) with:

```
A packaged `docker compose` install is planned for v0.1.
```

Replace that single line with:

```markdown
### Docker (recommended for non-developers)

PolicyCodex ships as a container. From the repo root:

```bash
cp .env.example .env          # set DJANGO_SECRET_KEY and your hostnames
./install.sh                  # builds the image and starts the stack
```

Open `http://localhost:8000` and complete the onboarding wizard.

- **State** (the SQLite database and cloned policy working copies) persists in the `policycodex-data` Docker volume.
- **Credentials** (the GitHub App private key and your LLM API key) stay on the host in `~/.config/policycodex/`, bind-mounted read-only into the container. They never enter the image or any committed file. Inside `~/.config/policycodex/config.env`, set `POLICYCODEX_GH_PRIVATE_KEY_PATH` to a `/secrets/...` path.
- A pre-built published image (no local build) is coming post-DISC; `docker-compose.pull.yml` is the placeholder for that path.
```

- [ ] **Step 2: Run the generic-ship guard (README is excluded, but confirm suite green)**

Run: `ai/venv/bin/python -m pytest`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(REPO-05): document the docker install path + secrets/volume model"
```

---

## Post-plan wrap (controller, after all tasks pass review)

These are controller bookkeeping steps, not subagent tasks:

- Mark REPO-05 **Resolved** in `PolicyWonk-v0.1-Tickets.md` with the commit range and a note that registry publishing remains a post-DISC follow-up, and that REPO-11 ratifies the `python:3.12-slim-bookworm` base pin.
- Append a REPO-05 event to `internal/PolicyWonk-Daily-Log.md`.
- Update `CLAUDE.md`: the `SECRET_KEY` hardening note (now done) and the Week-5 progress line.
- Note for REPO-11: the Docker base image pin (`python:3.12-slim-bookworm`) is now in place; REPO-11 finalizes `.python-version` / `python_requires` and the stable-vs-3.14 decision.

## Self-Review notes

- **Spec coverage:** (a) build-from-source compose → Task 5 `docker-compose.yml`; (b) published-image compose → Task 5 `docker-compose.pull.yml`; PT-free image → Task 4 Dockerfile + Task 7 guard; per-diocese config via mounted volume → Task 5 volumes + `.env.example`; AGPL "View Source" footer → Task 3; one-command install → Task 6; SECRET_KEY hardening (TODO at settings.py:37) → Task 1. All covered.
- **Decided forks honored:** hardening in scope (Task 1); Profile B stub validated by `docker compose config` (Task 5 Step 4) and structural test (Task 7); secrets via read-only bind mount (Task 5, zero code change thanks to existing `POLICYCODEX_CONFIG_PATH` support); footer URL configurable with placeholder (Tasks 1 + 3).
- **Type consistency:** helper names (`get_secret_key`, `get_debug`, `get_allowed_hosts`, `get_db_path`, `get_source_url`, `SettingsError`) are identical across `env.py`, the tests, and the settings wiring. Context value `source_url` matches between `core/context_processors.py` and `base.html`.
- **Docker-availability caveat:** Steps that need a docker daemon (Task 4 Step 4 build, Task 5 Step 4 `compose config`) are explicitly marked "run manually if no daemon"; the suite-level guards (Task 7) protect file contents regardless, so the plan still produces verifiable software without a daemon in the controller env.
