# REPO-11 Python Version Pin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the supported Python version so installs build against a known interpreter instead of whatever `python3` the host provides.

**Architecture:** Declare the floor (`>=3.12`, set by Django 6.0) and a single canonical target (`3.14`, matching the current dev environment). Make the pin load-bearing in the two places reproducibility depends on it — the `.python-version` file (host/clean-VM path) and the Docker base image (container path) — and add a structural regression test that keeps the two in lockstep and keeps the Django floor (which justifies the 3.12 floor) honest.

**Tech Stack:** Python 3.14, Django 6.0, plain `pathlib`/`re` file-scanning pytest tests (no Django app context — mirrors `tests/test_docker_packaging.py`).

**Decisions locked with Chuck (2026-06-07):**
- Standardize dev == prod on **Python 3.14**. This deliberately overrides REPO-05's note that "REPO-11 ratifies the `python:3.12-slim-bookworm` base pin" — the base image bumps to 3.14. The REPO-09 `sys.modules`/`@dataclass` 3.14 workaround stays load-bearing.
- Machine-readable pin is **`.python-version` only**. No `pyproject.toml`/`setup.py` is introduced (this is a Django app, not a distributed package, so `python_requires` has no natural home — YAGNI).
- Bump `app/requirements.txt` `django>=5.0` -> `django>=6.0` so the `>=3.12` floor is actually justified by the declared Django floor.
- Keep the existing `>=` floor style in requirements (per project convention; do not convert to exact pins).

**Out of scope (do not touch):**
- `install.sh` — the Docker install path enforces the interpreter via the base image, not the host; no Python preflight needed there.
- README prose — line 104 already states "Python 3.12+ (the floor set by Django 6.0)"; that remains accurate.
- `ai/requirements.txt`, `spike/requirements.txt` — no Django, no floor change needed.

**Verification interpreter:** run pytest as `ai/venv/bin/python -m pytest` (no root venv exists; system python lacks pytest).

**Pre-DISC manual check (not automatable in this env, note for Chuck):** `docker build` against `python:3.14-slim-bookworm` must be run once on a live docker daemon to confirm the tag resolves and the slim image still has the apt `git` package available. The structural test below only checks string consistency, not that the image builds.

---

## File Structure

- **Create:** `.python-version` — single line `3.14`. Read by pyenv/uv on the host and clean-VM quick-start path.
- **Create:** `tests/test_python_pin.py` — structural regression guard tying `.python-version` <-> Dockerfile base image <-> Django floor.
- **Modify:** `Dockerfile:3` — `FROM python:3.12-slim-bookworm` -> `FROM python:3.14-slim-bookworm`.
- **Modify:** `app/requirements.txt:1` — `django>=5.0` -> `django>=6.0`.

---

## Task 1: Regression test for the version pin (TDD red)

Write the guard first so it drives the three file changes. The test asserts the desired end state, so it fails now against the current 3.12 base image / `django>=5.0` floor / missing `.python-version`.

**Files:**
- Test: `tests/test_python_pin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_python_pin.py` with exactly this content:

```python
"""Guards that the Python version pin (REPO-11) stays consistent across the repo.

Plain file-scanning tests (no Django context), mirroring tests/test_docker_packaging.py.
The .python-version file and the Dockerfile base image must agree on the target
minor version, and the Django floor must justify the >=3.12 Python floor.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def test_python_version_file_declares_supported_minor():
    raw = _read(".python-version").strip()
    assert re.fullmatch(r"3\.\d+(\.\d+)?", raw), f"unexpected .python-version: {raw!r}"
    major, minor = (int(part) for part in raw.split(".")[:2])
    assert (major, minor) >= (3, 12), "floor is 3.12 (set by Django 6.0)"


def test_dockerfile_base_matches_python_version():
    pin = _read(".python-version").strip()
    pin_minor = ".".join(pin.split(".")[:2])
    match = re.search(r"FROM python:(\d+\.\d+)", _read("Dockerfile"))
    assert match, "Dockerfile has no pinned python base image"
    assert match.group(1) == pin_minor, (
        f"Dockerfile base {match.group(1)} != .python-version {pin_minor}"
    )


def test_django_floor_justifies_python_floor():
    # Django 6.0 is what sets the >=3.12 floor; the requirement must pin >=6.0
    # so the Python floor is actually justified by the declared Django floor.
    match = re.search(
        r"^django>=(\d+)\.(\d+)", _read("app/requirements.txt"),
        re.IGNORECASE | re.MULTILINE,
    )
    assert match, "app/requirements.txt does not pin a django floor"
    assert (int(match.group(1)), int(match.group(2))) >= (6, 0), (
        "django floor must be >=6.0 to justify the >=3.12 Python floor"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ai/venv/bin/python -m pytest tests/test_python_pin.py -v`
Expected: FAIL. `test_python_version_file_declares_supported_minor` and `test_dockerfile_base_matches_python_version` error with `FileNotFoundError` (no `.python-version` yet); `test_django_floor_justifies_python_floor` fails the `>=6.0` assertion (current floor is `django>=5.0`).

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_python_pin.py
git commit -m "test(repo-11): guard python-version <-> Dockerfile base <-> django floor"
```

---

## Task 2: Add the `.python-version` pin (TDD green, part 1)

**Files:**
- Create: `.python-version`

- [ ] **Step 1: Create the pin file**

Create `.python-version` containing exactly one line (minor-level so pyenv/uv resolve to the latest installed 3.14.x patch):

```
3.14
```

- [ ] **Step 2: Run the version-file test to verify it passes**

Run: `ai/venv/bin/python -m pytest tests/test_python_pin.py::test_python_version_file_declares_supported_minor -v`
Expected: PASS.

Note: `test_dockerfile_base_matches_python_version` still FAILS at this point (Dockerfile is still on 3.12) — that is fixed in Task 3.

---

## Task 3: Bump the Docker base image to match (TDD green, part 2)

**Files:**
- Modify: `Dockerfile:3`

- [ ] **Step 1: Change the base image**

In `Dockerfile`, change line 3 from:

```dockerfile
FROM python:3.12-slim-bookworm
```

to:

```dockerfile
FROM python:3.14-slim-bookworm
```

Leave every other line of the Dockerfile unchanged (the `apt-get install git`, collectstatic, and gunicorn entrypoint logic are version-independent).

- [ ] **Step 2: Run the Dockerfile-consistency test to verify it passes**

Run: `ai/venv/bin/python -m pytest tests/test_python_pin.py::test_dockerfile_base_matches_python_version -v`
Expected: PASS (`3.14` == `3.14`).

---

## Task 4: Bump the Django floor (TDD green, part 3)

**Files:**
- Modify: `app/requirements.txt:1`

- [ ] **Step 1: Raise the Django floor**

In `app/requirements.txt`, change the first line from:

```
django>=5.0
```

to:

```
django>=6.0
```

Leave the other eight requirement lines unchanged (keep their `>=` floor style).

- [ ] **Step 2: Run the django-floor test to verify it passes**

Run: `ai/venv/bin/python -m pytest tests/test_python_pin.py::test_django_floor_justifies_python_floor -v`
Expected: PASS.

- [ ] **Step 3: Run the full new test module**

Run: `ai/venv/bin/python -m pytest tests/test_python_pin.py -v`
Expected: 3 passed.

---

## Task 5: Full-suite regression check + commit

**Files:** none (verification + commit only)

- [ ] **Step 1: Run the whole suite to confirm no regressions**

Run: `ai/venv/bin/python -m pytest`
Expected: PASS — the prior suite count (~490) plus the 3 new tests, zero failures. In particular confirm `tests/test_docker_packaging.py` (which greps the Dockerfile) and `tests/test_generic_ship.py` still pass; neither asserts a specific Python minor, so the 3.12 -> 3.14 bump should not disturb them.

- [ ] **Step 2: Commit the pin + base image + floor together**

```bash
git add .python-version Dockerfile app/requirements.txt
git commit -m "feat(repo-11): pin Python 3.14 (.python-version + Docker base), raise django floor to >=6.0"
```

---

## Task 6: Record resolution in the ticket and CLAUDE.md

Docs-only. Keep entries spartan, active voice, no em dashes (project style).

**Files:**
- Modify: `PolicyWonk-v0.1-Tickets.md` (the REPO-11 row)
- Modify: `CLAUDE.md` (Current Status — REPO-11 moves out of "Remaining")

- [ ] **Step 1: Mark REPO-11 resolved in the tickets board**

In `PolicyWonk-v0.1-Tickets.md`, append a bold resolution note to the REPO-11 row describing: floor `>=3.12` (set by Django 6.0); standardized dev == prod on Python 3.14; added `.python-version` (`3.14`); bumped Docker base to `python:3.14-slim-bookworm` (overrides REPO-05's 3.12 ratification by Chuck's call); raised `app/requirements.txt` django floor to `>=6.0`; added `tests/test_python_pin.py` structural guard; REPO-09 3.14 workaround stays load-bearing; live `docker build` against 3.14-slim still owed pre-DISC. Record the new suite count.

- [ ] **Step 2: Update the Current Status paragraph in CLAUDE.md**

In `CLAUDE.md`, update the Week-5 progress so REPO-11 is no longer in the "Remaining: REPO-11/12, INGEST-05/06" list, with a one-clause summary of the pin, and refresh the suite count.

- [ ] **Step 3: Commit the docs**

```bash
git add PolicyWonk-v0.1-Tickets.md CLAUDE.md
git commit -m "docs(repo-11): record python 3.14 pin resolution"
```

---

## Self-Review

**Spec/ticket coverage (REPO-11 asks):**
- "Declare the floor (>=3.12, set by Django 6.0) and a target version" — floor asserted in `test_python_version_file_declares_supported_minor`; target `3.14` in `.python-version`. Floor justified by the `django>=6.0` bump (Task 4). Covered.
- "add the pin where it is load-bearing: the Docker base image (REPO-05)" — Task 3. Covered.
- "a `.python-version` and/or `python_requires`" — `.python-version` chosen; `python_requires` deliberately skipped (no packaging file, decided with Chuck). Covered.
- "and the clean-VM install path (REPO-10)" — README prose already documents 3.12+ (line 104, unchanged and still accurate); the clean-VM host path now also carries `.python-version`. Covered.
- "Decide whether to standardize dev on stable 3.12/3.13 vs bleeding-edge 3.14" — decided: 3.14, with the REPO-09 workaround acknowledged as load-bearing. Covered.

**Placeholder scan:** No TBD/TODO/"add appropriate X" steps. Every code/file step shows exact content. No "handle edge cases" hand-waves.

**Type/name consistency:** Test function names referenced in run commands (`test_python_version_file_declares_supported_minor`, `test_dockerfile_base_matches_python_version`, `test_django_floor_justifies_python_floor`) match their definitions in Task 1 verbatim. `.python-version` value `3.14` is consistent across Tasks 2, 3, and the Dockerfile assertion (minor-level `3.14`).
