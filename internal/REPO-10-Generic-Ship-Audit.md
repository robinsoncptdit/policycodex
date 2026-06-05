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
| 1 | `ai/taxonomies/pt_classification.yaml` | Header named the PT diocese, a PT repo SHA, and `internal/...pdf`. Seed read only by `spike/extract.py`. | Renamed -> `ai/taxonomies/seed_classification.example.yaml` (git rename, history preserved); header scrubbed to a generic dev-fixture note; spike re-pointed; `spike/eval/README.md` path updated. |
| 2 | `app/working_copy/checks.py:86` | E002 startup-check hint pointed to dev-only `internal/PolicyWonk-Foundational-Policy-Design.md`. | Hint genericized to "the foundational-policy design doc in the PolicyCodex project repository." |
| 3 | `repo-template/.github/workflows/build-handbook.yml:28` | Comment referenced `pt-policy run 26451196165`; vendored into every diocese repo. | Comment genericized to "Verified against a live GitHub Pages install." |

## Guard-coverage follow-up (from code review)

The guard's suffix allowlist initially omitted `.sh`, `.ts`, and `.css`. `repo-template/`
vendors `sync-handbook.sh` and `handbook/src/content.config.ts` verbatim into a diocese
repo, so a future leak there would have passed undetected. Added those suffixes and a
comment documenting the allowlist contract (a new shipping file type must be added to
`_SCANNED_SUFFIXES`). Both files are clean today; this closes the coverage hole.

## Deliberate non-changes (recorded, not changed)

- `README.md` — intentionally credits install-zero (Pensacola-Tallahassee) and the LA/Baltimore design reviewers. Ship-generic governs code, not factual credits.
- `spike/extract.py:69` prompt string names the PT diocese. `spike/` is a dev harness outside the audit grep scope; the prompt is held byte-stable to protect eval reproducibility (per the AI-12-revised daily-log note).
- Test fixtures naming PT (`app/git_provider/tests/test_github_provider.py`, `ingest/tests/test_extractors.py`, `spike/eval/*.jsonl`) — out of the ticket's "non-test" scope; the guard test excludes test files.

## Clean-VM verification (non-Docker)

Fresh `git clone` of the repo -> `python3 -m venv .venv` -> `pip install -r ai/requirements.txt
-r app/requirements.txt` -> `manage.py migrate` -> `manage.py runserver`. Python 3.14.5.
All steps succeeded with no error (pip emitted harmless cache-deserialization warnings only).

User-visible surfaces walked as an authenticated superuser, each scanned for the forbidden
token set:

| Surface | Result |
|---------|--------|
| `/onboarding/` (redirects to `/onboarding/github-repo/`, first wizard screen) | 200, no leak |
| `/catalog/` (title "Catalog \| PolicyCodex") | 200, no leak |
| `/health/` | 200, no leak |
| startup system-check (W001 working-copy warning) | generic ("the diocese's policy repo URL"), no leak |

Result: PASS - no PT/Pensacola/Tallahassee/internal leakage observed in any user-visible surface.

Scope note: a fresh clone has no policy repo synced, so the catalog is empty and the
`/policies/<slug>/` detail view + edit affordance have no live data to render (`/policies/`
and a bogus slug both 404 cleanly). The detail view (`core/views.py:policy_detail`,
`core/templates/policy_detail.html`) and its templates are covered by the static guard test
(`core` is one of the six scanned shipping roots) and were browser-verified during APP-23
development. The live walk here confirms the install path and the onboarding/catalog/health
surfaces render generically.

Deferred to REPO-05: the `docker compose up` install path. The Python version pin
exercised here (3.14.5) folds into REPO-11.
