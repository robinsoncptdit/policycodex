# REPO-05 Live `docker compose up` Validation Plan

> **For agentic workers:** This is a validation runbook, not a feature build. It is executed **inline by the controller** (it needs a live Docker daemon on Chuck's host, a one-time Colima install, and human observation of real container output). Do NOT dispatch subagents — they cannot drive the host daemon or judge runtime behavior better than the controller. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the REPO-05 container stack (`Dockerfile` + `docker-compose.yml` Profile A + `install.sh`) actually builds and boots a working PolicyCodex on a live Docker daemon, and that the Profile B stub (`docker-compose.pull.yml`) is config-valid. This is the "manual `docker compose up` check owed before DISC" called out in CLAUDE.md.

**Architecture:** Install Colima (headless Linux-VM Docker engine — the closest stand-in for the diocese VM the container ships to). Run the documented one-command install path exactly as a diocese IT director would (`./install.sh`). Curl the running app. Validate persistence and the Profile B stub. Fix any blocker found, re-run, then record the result.

**Tech Stack:** Colima + Docker CLI + Docker Compose v2 (Homebrew), Python 3.12-slim container, Django 5/6 + gunicorn + WhiteNoise, SQLite on a named volume.

**Scope note:** This validates the *generic* container boot only — empty DB, no diocese repo cloned, onboarding incomplete. The startup self-check (APP-21) is designed to downgrade "working copy missing" to a warning when `POLICYCODEX_ONBOARDING_COMPLETE` is falsy, so a clean boot is expected. Cloning a real diocese repo and running the wizard end-to-end is OUT of scope here.

---

## Likely findings (anticipated before running)

These are derived from reading the artifacts. The plan checks each explicitly.

1. **DB persistence gap (probable real bug).** `policycodex_site/env.py:48-50` defaults `POLICYCODEX_DB_PATH` to `BASE_DIR/db.sqlite3` (i.e. `/app/db.sqlite3`, inside the ephemeral image layer). The `docker-compose.yml` comment claims the SQLite DB persists in the `policycodex-data:/data` volume, but that only happens if `.env` sets `POLICYCODEX_DB_PATH=/data/db.sqlite3`. Task 5 verifies persistence and Task 6 fixes `.env.example` if the var is missing/wrong.
2. **Secrets dir may not exist.** The bind mount `${HOME}/.config/policycodex:/secrets:ro` (docker-compose.yml:16) will have Docker auto-create an empty host dir if it's absent — silent, but worth confirming it resolves rather than erroring under Colima. Task 2 ensures it exists.
3. **ALLOWED_HOSTS is fine.** `env.py:41-45` defaults to `localhost,127.0.0.1` when unset, so `curl localhost:8000` is expected to work without extra config. No action expected.
4. **Manifest-static build failure (possible).** Build-time `collectstatic` uses `CompressedManifestStaticFilesStorage` (settings.py:144-149); it hard-fails if any template `{% static %}`-references a file that isn't collected. Task 3 catches this at build.

---

## Task 1: Install and start the Colima Docker engine

**Files:** none (host setup).

- [ ] **Step 1: Install Colima + Docker CLI + Compose**

Run:
```bash
brew install colima docker docker-compose
```
Expected: brew completes; `colima`, `docker`, and the `docker-compose` plugin are installed. (If already installed, brew reports "already installed" — fine.)

- [ ] **Step 2: Start the Colima VM**

Run:
```bash
colima start
```
Expected: ends with `colima is running using macOS Virtualization.Framework` (or similar). First run downloads a VM image and takes a few minutes.

- [ ] **Step 3: Verify the daemon and Compose v2 are reachable**

Run:
```bash
docker version && docker compose version
```
Expected: both a `Client:` AND a `Server:` block from `docker version` (Server present = daemon reachable), and `Docker Compose version v2.x` from the second command.

If `docker compose version` works but `docker-compose` (hyphen) is what's on PATH, that's fine — `install.sh` and this plan use the v2 `docker compose` subcommand form.

---

## Task 2: Stage the host prerequisites the compose file expects

**Files:**
- Create (if absent): `${HOME}/.config/policycodex/` (host secrets dir, bind-mounted read-only)
- Create: `/Users/chuck/PolicyWonk/.env` (from `.env.example`)

- [ ] **Step 1: Ensure the secrets dir exists so the `:ro` bind mount resolves cleanly**

Run:
```bash
mkdir -p "${HOME}/.config/policycodex" && ls -ld "${HOME}/.config/policycodex"
```
Expected: the directory exists and is listed. (Per the credentials-stay-local convention, real GitHub App keys live here; for a generic boot test it may be empty.)

- [ ] **Step 2: Run the documented install once to generate `.env`**

Run from the repo root:
```bash
cd /Users/chuck/PolicyWonk && ./install.sh
```
Expected (first run): script prints "Created .env from .env.example. Edit it to set DJANGO_SECRET_KEY..." and exits 0 without building. This exercises the install.sh "no .env yet" branch (install.sh:16-21).

- [ ] **Step 3: Generate and set a real `DJANGO_SECRET_KEY` in `.env`**

The container has DEBUG off by default, so a non-empty secret key is mandatory (env.py:29-38) and `install.sh:23-28` blocks boot if it's empty. Generate one with the project venv:
```bash
ai/venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```
Then edit `/Users/chuck/PolicyWonk/.env`: set the `DJANGO_SECRET_KEY=` line to the printed value (use the Edit tool, not echo, to avoid shell-quoting issues with special characters in the key).

Expected: `.env` now has a non-empty `DJANGO_SECRET_KEY=...`.

- [ ] **Step 4: Read `.env` and confirm the DB path target**

Open `/Users/chuck/PolicyWonk/.env` and check whether `POLICYCODEX_DB_PATH` is set to a path under `/data`. Record the answer — it drives Task 6.
- If `POLICYCODEX_DB_PATH=/data/db.sqlite3` (or similar under `/data`): persistence is wired correctly; Task 6 becomes a no-op confirmation.
- If the var is absent or points outside `/data`: this is the anticipated persistence bug; Task 6 fixes it.

---

## Task 3: Build the image (Profile A)

**Files:** `Dockerfile`, `docker-compose.yml`.

- [ ] **Step 1: Build without cache to exercise the real first-install experience**

Run:
```bash
cd /Users/chuck/PolicyWonk && docker compose build --no-cache 2>&1 | tail -40
```
Expected: build completes through all stages, ending with a successful `naming to docker.io/library/policycodex:local` (or `=> => writing image`). The critical stage is `RUN ... collectstatic` (Dockerfile:26) — it must print "N static files copied/post-processed" and NOT raise `ValueError: Missing staticfiles manifest entry`.

- [ ] **Step 2: If the build fails at `collectstatic` (manifest entry missing)**

This means a template references a `{% static %}` file that isn't being collected. Diagnose:
```bash
grep -rn "{% static" /Users/chuck/PolicyWonk --include=*.html
```
Cross-check each referenced path exists under an app `static/` dir. Fix by either adding the missing asset or correcting the reference, then re-run Step 1. (Record the fix as a REPO-05 follow-up finding.)

- [ ] **Step 3: If the build fails installing Python deps**

Re-read the failing line. Most likely a pin issue in `app/requirements.txt` / `ai/requirements.txt` (all currently `>=` floors, so unlikely). Fix the offending constraint and re-run Step 1.

---

## Task 4: Boot the stack and confirm the app serves

**Files:** `docker-compose.yml`, `docker/entrypoint.sh`.

- [ ] **Step 1: Start detached via the documented one-command path**

Run:
```bash
cd /Users/chuck/PolicyWonk && ./install.sh
```
Expected: now that `.env` exists with a secret key, install.sh runs `docker compose up --build -d` (install.sh:31) and prints "PolicyCodex is starting at http://localhost:8000".

- [ ] **Step 2: Confirm the container reached the gunicorn stage**

Run:
```bash
docker compose logs app 2>&1 | tail -30
```
Expected, in order: Django migrate output ("Applying ... OK" lines from entrypoint.sh:5), no superuser creation (the three `DJANGO_SUPERUSER_*` vars are unset → skipped, entrypoint.sh:11-13), then gunicorn boot lines: `Starting gunicorn`, `Listening at: http://0.0.0.0:8000`, and 3 `Booting worker` lines (entrypoint.sh:15-17). No traceback.

- [ ] **Step 3: Confirm the container is healthy/running, not crash-looping**

Run:
```bash
docker compose ps
```
Expected: the `app` service shows state `Up` (not `Restarting`). `restart: unless-stopped` (docker-compose.yml:17) would mask a crash as a restart loop — if you see `Restarting`, go back to Step 2 logs.

- [ ] **Step 4: Hit the health endpoint**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health/
```
Expected: `200`. (Confirms gunicorn + WhiteNoise + URL routing + DB are all live end-to-end. `/health/` is the core app's health check.)

- [ ] **Step 5: Confirm DEBUG-off host handling and login redirect**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/
```
Expected: a redirect status (`302`) toward `/login/` (LOGIN_URL, settings.py:155), NOT `400 Bad Request`. A `400` would mean ALLOWED_HOSTS rejected `localhost` — unexpected given the env.py default, but if it happens, set `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1` in `.env` and re-run `docker compose up -d`.

- [ ] **Step 6: Confirm a static asset is served by WhiteNoise**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/static/admin/css/base.css
```
Expected: `200` (proves the build-time `collectstatic` output is served at runtime by the manifest storage).

---

## Task 5: Verify state persistence across a container recreate

This is the test that catches the anticipated DB-persistence bug from real behavior rather than by inspection.

- [ ] **Step 1: Create a superuser inside the running container (writes a DB row)**

Run:
```bash
docker compose exec app python manage.py createsuperuser --noinput \
  --username probe --email probe@example.com
```
Expected: "Superuser created successfully." (Password unset is fine — we only need a persisted row.)

- [ ] **Step 2: Confirm the row exists**

Run:
```bash
docker compose exec app python manage.py shell -c \
  "from django.contrib.auth import get_user_model as g; print(g().objects.filter(username='probe').count())"
```
Expected: `1`.

- [ ] **Step 3: Recreate the container (keeps the named volume, drops the container layer)**

Run:
```bash
cd /Users/chuck/PolicyWonk && docker compose down && docker compose up -d
```
Expected: container stops and is recreated. The `policycodex-data` volume is NOT removed (only `down -v` would do that).

- [ ] **Step 4: Re-check the row survived**

Run (after waiting for boot — re-run if it errors with "database is locked" during startup migrate):
```bash
docker compose exec app python manage.py shell -c \
  "from django.contrib.auth import get_user_model as g; print(g().objects.filter(username='probe').count())"
```
Expected: `1` if persistence is correctly wired to `/data`. **If it returns `0`, the DB is living in the ephemeral image layer — the anticipated bug — proceed to Task 6.**

---

## Task 6: Fix DB persistence if Task 5 Step 4 returned 0

Skip this entire task if Task 5 Step 4 returned `1`.

**Files:**
- Modify: `/Users/chuck/PolicyWonk/.env.example` (add the persistent DB path)
- Modify: `/Users/chuck/PolicyWonk/.env` (local copy, to re-test)

- [ ] **Step 1: Add the persistent DB path to `.env.example`**

The container persists state under `/data` (the `policycodex-data` volume). Point the DB there. Add (or correct) this line in `.env.example`, in the deploy-knobs section near the other `POLICYCODEX_*` vars:
```
# SQLite database file. Keep this under /data so it persists in the
# policycodex-data volume across container rebuilds (REPO-05).
POLICYCODEX_DB_PATH=/data/db.sqlite3
```

- [ ] **Step 2: Mirror the change into the live `.env` and recreate**

Add the same `POLICYCODEX_DB_PATH=/data/db.sqlite3` line to `/Users/chuck/PolicyWonk/.env`, then:
```bash
cd /Users/chuck/PolicyWonk && docker compose down && docker compose up -d
```
Expected: migrate runs against `/data/db.sqlite3` on boot (visible in `docker compose logs app`).

- [ ] **Step 3: Re-run the persistence proof**

Repeat Task 5 Steps 1-4. Expected: Step 4 now returns `1`.

- [ ] **Step 4: Commit the fix**

```bash
cd /Users/chuck/PolicyWonk && git add .env.example && git commit -m "fix(repo-05): persist SQLite DB on the data volume (POLICYCODEX_DB_PATH=/data)"
```

---

## Task 7: Validate the Profile B published-image stub is config-valid

The image isn't published yet, so this only confirms the compose file parses and resolves — exactly what the file's own comment promises (docker-compose.pull.yml:3-4).

- [ ] **Step 1: Validate the Profile B compose config**

Run:
```bash
cd /Users/chuck/PolicyWonk && docker compose -f docker-compose.pull.yml config >/dev/null && echo "PROFILE-B-CONFIG-OK"
```
Expected: prints `PROFILE-B-CONFIG-OK` with no YAML/interpolation errors (it should resolve `${HOME}` and the `policycodex-data` volume). We do NOT run `up` on this file — the `ghcr.io/policycodex/policycodex:latest` image does not exist yet.

---

## Task 8: Tear down and record the result

- [ ] **Step 1: Stop the stack (preserve the volume)**

Run:
```bash
cd /Users/chuck/PolicyWonk && docker compose down
```
Expected: containers + network removed; `policycodex-data` volume retained.

- [ ] **Step 2: Optionally stop Colima to free host resources**

Run (optional):
```bash
colima stop
```

- [ ] **Step 3: Record the outcome**

Append a dated entry to `internal/PolicyWonk-Daily-Log.md` capturing: build result, boot result, the four curl status codes, persistence verdict, any fix committed (Task 6), and Profile B config result. Update the REPO-05 line in `CLAUDE.md` to drop "NOT yet validated on a live docker daemon" and state it was validated on Colima on 2026-06-07 (note Colima as the engine, since that is the validation surface, not Docker Desktop).

- [ ] **Step 4: Commit the docs update**

```bash
cd /Users/chuck/PolicyWonk && git add CLAUDE.md internal/PolicyWonk-Daily-Log.md && git commit -m "docs(repo-05): record live docker compose validation on Colima"
```

---

## Self-review checklist (for the controller before executing)

- Every command targets a real artifact confirmed by reading: `Dockerfile`, `docker-compose.yml`, `docker-compose.pull.yml`, `install.sh`, `docker/entrypoint.sh`, `policycodex_site/settings.py`, `policycodex_site/env.py`.
- The one likely code/config change (DB persistence) is gated behind an observed failure (Task 5 Step 4 = 0), not applied blindly — so if `.env.example` already sets `/data`, nothing changes.
- No reliance on `cat`/`echo` to write `.env`; secret-key edit uses the Edit tool (special chars in keys break shell quoting).
- Out-of-scope (full wizard / real diocese clone) is stated so the boot test isn't mistaken for end-to-end onboarding validation.
