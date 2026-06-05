# REPO-10 Generic-Ship Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every PT-specific name and dev-only `internal/` path from the shipping codebase, add a permanent regression guard that keeps it generic, and verify a clean install shows nothing PT-flavored.

**Architecture:** The live read paths are already generic (AI-12-revised moved taxonomy reads to the foundational bundle, found by capability not slug). What remains are three stale string leaks in shipping files plus the dev seed file's PT-named header. We add one pure-pytest guard test that scans the shipping dirs for forbidden tokens, fix the leaks it finds, then run a non-Docker clean-VM verification (the `docker compose up` variant is deferred to REPO-05) and record findings in a worksheet.

**Tech Stack:** Python 3.14 / pytest (run via `ai/venv/bin/python -m pytest`), Django 6.0, PyYAML. No new dependencies.

**Scope decisions locked with Chuck (2026-06-05):**
- Clean-VM run: **non-Docker equivalent now** (clone + venv + migrate + runserver + wizard/catalog/detail walkthrough); defer the `docker compose up` run to when REPO-05 lands.
- Seed file: **genericize + rename** `ai/taxonomies/pt_classification.yaml` -> `ai/taxonomies/seed_classification.example.yaml`, scrub the header, re-point the spike.
- Test fixtures: **leave, record only.** PT names in `*/tests/*` are out of the ticket's "non-test" scope; the guard test excludes test files.

**Known shipping leaks the audit found (the cleanup target):**
1. `ai/taxonomies/pt_classification.yaml` header names "Diocese of Pensacola-Tallahassee", a PT repo SHA (`...pt-policy@34a1671`), and `internal/Document Retention Policy.pdf`. Consumed only by `spike/extract.py` as the seed fallback.
2. `app/working_copy/checks.py:86` — an `E002` startup-check hint points operators to `internal/PolicyWonk-Foundational-Policy-Design.md`, a path that exists only in the dev repo, not in an installed diocese.
3. `repo-template/.github/workflows/build-handbook.yml:28` — a comment "Verified on the first live install (pt-policy run 26451196165)." vendored into every diocese repo.

**Deliberate non-changes (record in worksheet, do NOT edit):**
- `README.md` PT mentions — intentional; the README credits install-zero (Pensacola-Tallahassee) and the design reviewers (LA, Baltimore). Ship-generic governs code, not factual credits.
- `spike/extract.py:69` prompt string `"## Diocese taxonomy reference (Diocese of Pensacola-Tallahassee)"` — `spike/` is a dev harness outside the ticket's grep scope, and the daily log records that the prompt rendering is held byte-stable to avoid eval drift. Editing it risks the spike's eval reproducibility for zero ship benefit.
- Test fixtures: `app/git_provider/tests/test_github_provider.py` (`pat@diocese-pt.example`), `ingest/tests/test_extractors.py` ("Diocese of Pensacola-Tallahassee"), `spike/eval/*.jsonl`. Out of scope per the ticket.

---

## File Structure

- **Create:** `tests/test_generic_ship.py` — repo-root, Django-free pytest module. The permanent regression guard: scans the six shipping roots for forbidden diocese-name and dev-path tokens. One clear responsibility (the ship-generic invariant); lives at repo root because it spans the whole repo, not one app.
- **Rename + modify:** `ai/taxonomies/pt_classification.yaml` -> `ai/taxonomies/seed_classification.example.yaml` (header scrub only; YAML payload unchanged).
- **Modify:** `spike/extract.py` (line 49 seed path + a `spike/eval/README.md` prose reference) to follow the rename.
- **Modify:** `app/working_copy/checks.py` (the `E002` hint string).
- **Modify:** `repo-template/.github/workflows/build-handbook.yml` (the preflight comment).
- **Create:** `internal/REPO-10-Generic-Ship-Audit.md` — the worksheet: each finding + resolution + the clean-VM run notes.
- **Modify (closeout doc sweep):** `CLAUDE.md` (line ~114 seed-file note), `PolicyWonk-v0.1-Tickets.md` (REPO-10 row -> Resolved), `internal/PolicyWonk-Daily-Log.md` (event entry).

---

### Task 1: Generic-ship leakage guard test (RED)

**Files:**
- Create: `tests/test_generic_ship.py`

This is the spec for the cleanup: it must FAIL first, listing the three known leaks. We leave it red until Task 2's fixes turn it green.

- [ ] **Step 1: Write the guard test**

Create `tests/test_generic_ship.py` with exactly this content:

```python
"""REPO-10 generic-ship guard.

PolicyCodex ships as a generic, diocese-agnostic codebase. No shipping
file may name the install-zero diocese (Pensacola-Tallahassee) or point at
the dev-only `internal/` document tree, because those names and paths do
not exist in an installed diocese instance. This test enforces that
invariant so a future hardcode is caught in the suite, not on a customer's
VM.

Scope mirrors the REPO-10 ticket grep: the shipping app/library dirs plus
the vendored `repo-template/`. Out of scope (and excluded): test files,
`internal/`, `archive/`, the `spike/` dev harness, `README.md` (which
intentionally credits install zero), and this file.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Dirs whose contents are part of the shipping artifact and must stay generic.
_SHIPPING_ROOTS = ("app", "core", "ai", "ingest", "policycodex_site", "repo-template")

_SCANNED_SUFFIXES = {
    ".py", ".yaml", ".yml", ".html", ".md", ".txt",
    ".cfg", ".ini", ".astro", ".mjs", ".js", ".json",
}

# A path containing any of these parts is skipped.
_EXCLUDED_PARTS = {"tests", "__pycache__", "node_modules", "dist", ".astro", "venv"}

# Diocese-name and dev-path tokens that must never appear in a shipping file.
_FORBIDDEN = (
    re.compile(r"pensacola", re.IGNORECASE),
    re.compile(r"tallahassee", re.IGNORECASE),
    re.compile(r"pt-policy", re.IGNORECASE),
    re.compile(r"pt_classification", re.IGNORECASE),
    # Dev-only doc tree, never present in an installed instance. Narrow so the
    # bare word "internal" (e.g. "internal server error") does not trip it.
    re.compile(r"internal/(?:PolicyWonk|PolicyCodex|REPO-|Document |superpowers/)"),
)


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name == "tests.py" or name.startswith("test_") or name.endswith("_test.py")


def _scanned_files():
    for root in _SHIPPING_ROOTS:
        root_dir = _REPO_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in _SCANNED_SUFFIXES:
                continue
            if _is_test_file(path):
                continue
            if any(part in _EXCLUDED_PARTS for part in path.parts):
                continue
            yield path


def test_no_pt_or_internal_path_leakage_in_shipping_code():
    leaks = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in _FORBIDDEN:
                if pattern.search(line):
                    rel = path.relative_to(_REPO_ROOT)
                    leaks.append(f"{rel}:{line_no}: {line.strip()}")
    assert not leaks, "Generic-ship leak(s) found:\n" + "\n".join(leaks)
```

- [ ] **Step 2: Run the guard test and confirm it FAILS with the known leaks**

Run: `ai/venv/bin/python -m pytest tests/test_generic_ship.py -v`
Expected: FAIL. The assertion message must list lines from exactly these three files (one or more lines each):
- `ai/taxonomies/pt_classification.yaml:...` (pensacola/tallahassee + pt-policy + internal/Document hits)
- `app/working_copy/checks.py:86` (internal/PolicyWonk hit)
- `repo-template/.github/workflows/build-handbook.yml:28` (pt-policy hit)

If any OTHER file appears, stop and report it — it is a leak the audit did not anticipate and needs a decision before proceeding. Do not commit; this red test is the cleanup spec for Task 2.

---

### Task 2: Genericize the three leaks and turn the guard green

**Files:**
- Rename + modify: `ai/taxonomies/pt_classification.yaml` -> `ai/taxonomies/seed_classification.example.yaml`
- Modify: `spike/extract.py:49`, `spike/eval/README.md:31`
- Modify: `app/working_copy/checks.py:83-87`
- Modify: `repo-template/.github/workflows/build-handbook.yml:26-28`
- Test: `tests/test_generic_ship.py`, `spike/test_extract_taxonomy.py`, `app/working_copy/tests/test_checks.py`

- [ ] **Step 1: Rename the seed file (preserve history)**

Run: `git mv ai/taxonomies/pt_classification.yaml ai/taxonomies/seed_classification.example.yaml`

- [ ] **Step 2: Scrub the seed file header**

In `ai/taxonomies/seed_classification.example.yaml`, replace the entire leading comment block (the original lines 1-18, everything above `classifications:`) with this generic header. Leave the `classifications:` / `retention_schedule:` payload below it completely unchanged:

```yaml
# Example classification + retention seed (development fixture).
#
# Generic seed used ONLY by the extraction spike (spike/extract.py) when no
# live foundational bundle is available (POLICYCODEX_POLICIES_DIR unset). This
# is NOT shipped configuration. A real diocese's classifications and retention
# schedule live in its policy repo as policies/document-retention/data.yaml
# (the foundational-policy bundle), which the app and AI extraction read by
# capability (`provides:`), never from this file.
#
# Classifications and retention_schedule are independent axes. Retention values
# are free-text strings; v0.1 does not normalize them.
```

- [ ] **Step 3: Re-point the spike to the renamed seed**

In `spike/extract.py`, change line 49 from:

```python
SEED_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "ai" / "taxonomies" / "pt_classification.yaml"
```

to:

```python
SEED_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "ai" / "taxonomies" / "seed_classification.example.yaml"
```

- [ ] **Step 4: Fix the stale path in the spike eval README**

In `spike/eval/README.md`, line ~31, replace the substring `ai/taxonomies/pt_classification.yaml` with `ai/taxonomies/seed_classification.example.yaml` (one occurrence; leave the surrounding prose intact).

- [ ] **Step 5: Genericize the E002 hint in the startup self-check**

In `app/working_copy/checks.py`, replace the hint block (lines 83-87):

```python
                hint=(
                    f"Add a policy bundle whose policy.md declares `foundational: true` "
                    f"and `provides: [{capability}, ...]`. See "
                    "internal/PolicyWonk-Foundational-Policy-Design.md."
                ),
```

with:

```python
                hint=(
                    f"Add a policy bundle whose policy.md declares `foundational: true` "
                    f"and `provides: [{capability}, ...]`. See the foundational-policy "
                    "design doc in the PolicyCodex project repository."
                ),
```

- [ ] **Step 6: Genericize the build-handbook preflight comment**

In `repo-template/.github/workflows/build-handbook.yml`, replace the three-line comment (lines 26-28):

```yaml
      # `pages: read` is required for `gh api repos/$REPO/pages`; without it
      # the call returns 403 and the gate silently flips to skip-deploy.
      # Verified on the first live install (pt-policy run 26451196165).
```

with:

```yaml
      # `pages: read` is required for `gh api repos/$REPO/pages`; without it
      # the call returns 403 and the gate silently flips to skip-deploy.
      # Verified against a live GitHub Pages install.
```

- [ ] **Step 7: Confirm no remaining reference to the old seed name in shipping/spike code**

Run: `grep -rn "pt_classification" app/ core/ ai/ ingest/ policycodex_site/ repo-template/ spike/ | grep -v __pycache__`
Expected: no output (empty). Remaining matches under `internal/` and `archive/` are historical records and are left as-is.

- [ ] **Step 8: Run the guard test — now GREEN**

Run: `ai/venv/bin/python -m pytest tests/test_generic_ship.py -v`
Expected: PASS (no leaks).

- [ ] **Step 9: Run the touched-area tests**

Run: `ai/venv/bin/python -m pytest spike/test_extract_taxonomy.py app/working_copy/tests/test_checks.py repo-template/tests/test_build_handbook.py -v`
Expected: PASS. In particular `test_extract_defaults_to_seed_taxonomy` still passes (it reloads `extract` and asserts `_taxonomy_source == "seed"` and 8 classifications; the rename keeps the payload identical, and it never references the filename).

- [ ] **Step 10: Run the full suite**

Run: `ai/venv/bin/python -m pytest`
Expected: PASS, count one higher than the 435 baseline (the new guard test): 436 green.

- [ ] **Step 11: Commit**

```bash
git add tests/test_generic_ship.py ai/taxonomies/seed_classification.example.yaml spike/extract.py spike/eval/README.md app/working_copy/checks.py repo-template/.github/workflows/build-handbook.yml
git commit -m "$(cat <<'EOF'
feat(repo): generic-ship guard + scrub PT/internal-path leaks (REPO-10)

Add tests/test_generic_ship.py guarding the six shipping roots against
diocese-name and dev-only internal/ path tokens. Rename the spike seed
ai/taxonomies/pt_classification.yaml -> seed_classification.example.yaml
with a generic header, genericize the E002 startup-check hint and the
vendored build-handbook preflight comment.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Clean-VM (non-Docker) verification + worksheet + doc sweep

**Files:**
- Create: `internal/REPO-10-Generic-Ship-Audit.md`
- Modify: `CLAUDE.md`, `PolicyWonk-v0.1-Tickets.md`, `internal/PolicyWonk-Daily-Log.md`

> **Note for the executor:** Steps 1-2 are an OPERATIONAL verification (fresh clone + running server + browser walkthrough). They are best run by the controller or by Chuck, not a sandboxed code subagent. If you are a code subagent, draft the worksheet (Step 3) from the static findings and mark the clean-VM run section "pending controller run," then hand back.

- [ ] **Step 1: Stand up a clean checkout**

```bash
rm -rf /tmp/policycodex-cleanvm && git clone /Users/chuck/PolicyWonk /tmp/policycodex-cleanvm && cd /tmp/policycodex-cleanvm
python3 -m venv .venv && .venv/bin/pip install -U pip
.venv/bin/pip install -r ai/requirements.txt -r app/requirements.txt
.venv/bin/python manage.py migrate
```
Expected: clone succeeds, deps install, migrations apply with no error. (Record the exact requirements files used; REPO-11 will canonicalize the install path and the Python pin.)

- [ ] **Step 2: Walk the user-visible surfaces, watching for PT / internal/ leakage**

Run: `.venv/bin/python manage.py runserver` and in a browser visit, in order:
- `/onboarding/` and step through the wizard screens
- `/catalog/`
- a `/policies/<slug>/` detail view
- the edit affordance on a non-foundational row

Expected: no occurrence of "PT", "Pensacola", "Tallahassee", or any `internal/...` path anywhere user-visible (page text, form labels, error messages, flash messages). Note any finding with its screen + exact string. (Browser tooling: claude-in-chrome MCP, loaded via ToolSearch.) Stop `runserver` when done; `rm -rf /tmp/policycodex-cleanvm`.

- [ ] **Step 3: Write the REPO-10 worksheet**

Create `internal/REPO-10-Generic-Ship-Audit.md` with this content (fill the clean-VM result line from Step 2):

```markdown
# REPO-10 Generic-Ship Audit Worksheet

Date: 2026-06-05. Auditor: Scarlet. Suite at close: 436.

## Method

Grepped the shipping roots (`app/`, `core/`, `ai/`, `ingest/`, `policycodex_site/`,
`repo-template/`) for `pensacola`, `tallahassee`, `pt-policy`, `pt_classification`,
and dev-only `internal/` doc paths, excluding test files. Codified the grep as a
permanent regression guard (`tests/test_generic_ship.py`). Then ran a non-Docker
clean-VM verification (the `docker compose up` variant is deferred to REPO-05).

## Findings and resolutions

| # | Location | Finding | Resolution |
|---|----------|---------|------------|
| 1 | `ai/taxonomies/pt_classification.yaml` | Header named the PT diocese, a PT repo SHA, and `internal/...pdf`. Seed read only by `spike/extract.py`. | Renamed -> `ai/taxonomies/seed_classification.example.yaml`; header scrubbed to a generic dev-fixture note; spike re-pointed. |
| 2 | `app/working_copy/checks.py:86` | E002 startup-check hint pointed to dev-only `internal/PolicyWonk-Foundational-Policy-Design.md`. | Hint genericized to "the foundational-policy design doc in the PolicyCodex project repository." |
| 3 | `repo-template/.github/workflows/build-handbook.yml:28` | Comment referenced `pt-policy run 26451196165`; vendored into every diocese repo. | Comment genericized to "Verified against a live GitHub Pages install." |

## Deliberate non-changes (recorded, not changed)

- `README.md` — intentionally credits install-zero (Pensacola-Tallahassee) and the LA/Baltimore design reviewers. Ship-generic governs code, not factual credits.
- `spike/extract.py:69` prompt string names the PT diocese. `spike/` is a dev harness outside the audit grep scope; the prompt is held byte-stable to protect eval reproducibility (per the AI-12-revised daily-log note).
- Test fixtures naming PT (`app/git_provider/tests/test_github_provider.py`, `ingest/tests/test_extractors.py`, `spike/eval/*.jsonl`) — out of the ticket's "non-test" scope; the guard test excludes test files.

## Clean-VM verification (non-Docker)

Fresh `git clone` -> venv -> `pip install -r ai/requirements.txt -r app/requirements.txt`
-> `manage.py migrate` -> `runserver`. Walked `/onboarding/`, `/catalog/`,
`/policies/<slug>/`, and a non-foundational edit affordance.

Result: <PASS - no PT/internal leakage observed | FAIL - record findings here>

Deferred to REPO-05: the `docker compose up` install path. The Python version pin
exercised here folds into REPO-11.
```

- [ ] **Step 4: Doc sweep**

- In `CLAUDE.md` (the seed-file line, ~114), update the `ai/taxonomies/pt_classification.yaml` reference to note REPO-10 resolved it: renamed to `ai/taxonomies/seed_classification.example.yaml`, a clearly-labeled dev seed fixture.
- In `PolicyWonk-v0.1-Tickets.md`, mark the REPO-10 row Resolved with a one-line summary (guard test + three genericizations + non-Docker clean-VM run; Docker variant deferred to REPO-05) and the commit SHA from Task 2.
- Append an event entry to `internal/PolicyWonk-Daily-Log.md` (date, what landed, suite 435 -> 436, the three resolutions, the deferred Docker run).

- [ ] **Step 5: Commit**

```bash
git add internal/REPO-10-Generic-Ship-Audit.md CLAUDE.md PolicyWonk-v0.1-Tickets.md internal/PolicyWonk-Daily-Log.md
git commit -m "$(cat <<'EOF'
docs(REPO-10): generic-ship audit worksheet + clean-VM verification + closeout

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**1. Spec coverage (against the REPO-10 ticket's four scope items):**
- (1) Grep `app/`/`core/`/`ai/`/`ingest/`/`policycodex_site/` for PT tokens; route hits through config -> Task 1 codifies the grep as a test over those dirs (plus `repo-template/`); Task 2 resolves every hit. Covered.
- (2) Confirm `pt_classification.yaml` moved OR is a clearly-labeled fixture -> Task 2 renames + relabels it a dev fixture (live config already lives in the bundle per AI-12-revised). Covered.
- (3) Error messages / log lines / comments use "the diocese" generically -> Task 2 fixes the E002 hint and the build-handbook comment; guard test prevents regressions. Covered.
- (4) Clean-VM run sees no PT/Pensacola/internal leakage -> Task 3 runs the non-Docker equivalent now; Docker variant explicitly deferred to REPO-05 and recorded. Covered (with documented deferral).
- Worksheet of findings + resolutions -> Task 3 Step 3. Covered.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases". Every code step shows the exact before/after text. The one fill-in (clean-VM PASS/FAIL line) is an observed result, not a code placeholder.

**3. Type/string consistency:** Renamed path string `ai/taxonomies/seed_classification.example.yaml` is used identically in the `git mv` target, `spike/extract.py:49`, the eval-README edit, and the grep verification. The guard test's `_FORBIDDEN` patterns match exactly the three known leaks and nothing else after the fixes (verified the narrow `internal/` regex avoids the bare word "internal"). `spike/test_extract_taxonomy.py` asserts behavior (`_taxonomy_source`, 8 classifications), not the filename, so the rename keeps it green.
