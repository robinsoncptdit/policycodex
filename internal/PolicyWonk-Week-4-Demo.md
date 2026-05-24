# PolicyCodex Week 4 Demo

**Sprint dates planned:** Monday, May 25, 2026 through Friday, May 29, 2026
**Actual execution window:** Sunday, May 24, 2026 (both waves in one day, ahead of the Monday start)
**Operating model:** Agent-led (per `internal/superpowers/specs/2026-05-05-agent-led-execution-design.md`). Wave 2 ran in auto mode (Scarlet drove design -> plan -> dispatch -> two-stage review -> in-branch fix -> merge autonomously, pausing only for human smokes).

## Summary

Week 4 closed all 10 Committed tickets across two waves, plus the live install and verification of the repo-side automation on the real diocese repo. The headline: the foundational-policy story is now end-to-end and **proven on `pt-policy`**, not just locally.

- **The merge-to-handbook loop is live.** PUBLISH-06 vendored the Astro handbook + a GitHub Actions build into `repo-template/`; it is installed on `pt-policy` and, on a merge to `main`, builds the handbook from the diocese's real `policies/` and uploads a Pages artifact. Verified green on the real repo.
- **The four-layer foundational-policy protection is real.** L1 UI gate (APP-20) hides edit/delete on foundational rows in the catalog (the detail-view gate is APP-23, Week 5); L2 CI guard (REPO-09) is installed on `pt-policy` and was live-proven to fail a PR that empties a foundational `provides:`; L3 startup self-check (APP-21, Week 3) still guards boot. L0 branch protection (REPO-08) underpins it.
- **Gap detection surfaces uncovered policies** (AI-13): the catalog flags any policy whose type is not in the diocese's retention classification taxonomy.
- **The onboarding wizard exists and has its first real screen.** APP-08 shipped the seven-step skeleton; APP-09 added screen 1 (GitHub repo: connect-existing or create-new) plus a reusable per-screen form pattern for APP-10..16.
- **Live taxonomy sync** (AI-12-revised): AI extraction now reads the diocese's foundational bundle `data.yaml` from the working copy, so a CFO edit flows into the next extraction.

Test suite went from 265 on main at Week-3 close to **373** at Week-4 close (+108).

## What is demoable now

1. **Catalog** (`/catalog/`): policies render with kind + gate badges; foundational rows show the typed-table banner and no edit/delete affordance (L1); any policy whose category is not in the retention taxonomy shows a "no retention match" badge with a count banner (AI-13).
2. **Edit -> Drafted -> Reviewed -> Published** (Week 3, still live): edit a non-foundational policy -> opens a PR -> Approve -> Publish squash-merges.
3. **Merge -> handbook build (LIVE on `pt-policy`)**: the publish merge triggers GitHub Actions, which builds the Astro handbook from `policies/` and uploads the artifact. Show the green run on the real repo.
4. **The guard blocks a bad edit (LIVE on `pt-policy`)**: a PR that deletes a foundational policy or empties its `provides:` fails the `foundational-guard` check. Demonstrated live.
5. **Onboarding wizard** (`/onboarding/`): step through the seven-screen flow; screen 1 captures + validates the GitHub repo choice into session state.

## Tickets Merged

### Wave 1 (executed Sun May 24; plan: Mon May 25)

| Ticket | Merge SHA | Notes |
|---|---|---|
| APP-20 L1 UI delete-gate | `7493be1` | Catalog-only foundational gate: foundational rows show the typed-table banner and no edit/delete affordance; Publish stays outside the gate. Detail-view half split to new ticket APP-23. 5 new tests. |
| REPO-09 L2 CI guard | `2f36986` | Generic vendorable guard in a new top-level `repo-template/`: a GitHub Action blocking any PR that deletes a `foundational: true` file or empties a `provides:` list. Standalone PyYAML-only script. 17 tests. Set the placement precedent PUBLISH-06 followed. |
| AI-12-revised Retention bundle read | `507eb1b` | New Django-free `ai/taxonomy_loader.py` finds the foundational bundle by capability and reads its `data.yaml` from the working copy (seed fallback). Closes the live-sync loop; prompt unchanged so no eval drift. 10 tests. |
| APP-08 Onboarding wizard skeleton | `fb20b78` | New `app/onboarding/` app: custom session-backed multi-step (no formtools, no DB), seven-step registry + nav + GET ahead-jump gating. Brainstormed first (custom-vs-formtools, session-vs-DB). 25 tests. |
| AI-07 Confidence audit emitter | `539f044` | New `ai/audit.py` `to_audit_yaml`, the inverse of `emit.py`: keeps only confidence scores in a `<slug>.audit.yaml` sidecar (spec line 99). Nested `confidence:` shape (locked with Chuck). Pure function; no file I/O or slug logic (deferred to AI-10). 10 tests. |
| INGEST-04 Source manifest data model | `f9535aa` | New `ingest/manifest.py`: frozen `ManifestEntry` (path, SHA-256 content hash, mtime, source label) + `entry_for`/`build_manifest`/`to_dict`/`from_dict`. The content hash is INGEST-05's change-detection key. 7 tests. |
| APP-22 `_resolve_repo` refactor | `8c89680` | Behavior-preserving extraction of `_origin_url` + `_resolve_repo` in `github_provider.py` (net -49 lines); the get-url block + `get_repo` now appear once. The ticket's method list was wrong; the plan documents the real duplication. Module tests unchanged. |

### Wave 2 (executed Sun May 24; plan: Wed May 27)

| Ticket | Merge SHA | Notes |
|---|---|---|
| PUBLISH-06 Handbook build workflow | `2ff22d4` | Vendored the Astro handbook + `build-handbook.yml` into `repo-template/`; on push to `main` touching `policies/**` or `handbook/**`, stages policies into the content dir, `npm ci/build/verify`, uploads a Pages artifact (build-and-upload only; serving is PUBLISH-07). Plus `sync-handbook.sh` re-vendor script + generalized `verify-build.mjs`. 7 structural tests. Two decisions locked with Chuck (vendor-into-template; build+artifact-only). |
| AI-13 Retention gap detection | `bd4ef9c` | Django-free `ai/gap_detection.py` + catalog banner + per-row badge. Gap = a policy whose `category` is not in the bundle `classifications` (by id/name, case-insensitive); free-text `retention_schedule` rows are not used for per-policy matching in v0.1. Reuses `taxonomy_loader`. Degrades to off when no bundle / on load error. 14 tests. |
| APP-09 Wizard screen 1 (GitHub repo) | `7350386` | `app/onboarding/forms.py` `GitHubRepoForm` (connect-existing vs create-new + branch) + a slug->form registry the generic view binds/validates/persists to `WizardState` (the per-screen pattern for APP-10..16). Capture-only: no clone/create mid-wizard (deferred to APP-15/16). 13 tests. |

## Live `pt-policy` verification (this sprint)

Done on the real diocese repo, with Chuck's authorization, driven by Scarlet:

| Action | Result |
|---|---|
| Install PUBLISH-06 + REPO-09 automation (PR #2) | Merged `41c6085` (GitHub-signed squash; satisfies the ruleset). `pt-policy` main now carries `.github/` + `handbook/`. |
| PUBLISH-06 build smoke | The merge triggered Build handbook: green in ~22s, built from PT's real `document-retention` bundle, uploaded the `github-pages` artifact. |
| REPO-09 guard smoke (PR #3) | A throwaway PR emptying `document-retention`'s `provides:` **failed** the `foundational-guard` check in 8s with the exact intended message. Closed unmerged. |
| Node 24 action bump (PR #4) | Bumped both workflows to `checkout@v6` / `setup-node@v6` / `setup-python@v6` / `upload-pages-artifact@v5` (registry-verified Node 24) in `repo-template` + live `pt-policy`; a triggered Build handbook ran green on Node 24 with no deprecation warning. |

The two `pt-policy` merges that hit the protected `main` used a temporary repository-admin bypass on the ruleset (`--admin` does not bypass repository rulesets, and Scarlet was the PR author so could not self-approve), and the ruleset was restored to its exact prior state immediately after each (`enforcement: active`, `bypass_actors: []`, all 5 rules). Verified.

## Architectural and process commitments (this sprint)

- **Auto mode works for a full wave.** Scarlet ran all of Wave 2 (design doc -> writing-plans -> worktree implementer -> two-stage review -> in-branch fix -> merge) autonomously, surfacing key decisions and pausing only for the human-authorized real-repo smokes. Kept the same discipline as supervised waves.
- **Commit the design + plan before dispatch.** Doing so made AI-13 and APP-09 fast-forward cleanly; PUBLISH-06 (dispatched before its design doc was committed) needed a `--no-ff` merge. Adopt commit-before-dispatch going forward.
- **The four-layer foundational-policy protection is now real and partly live.** L1 (APP-20) + L2 (REPO-09, live-proven on `pt-policy`) + L3 (APP-21) + L0 (REPO-08).
- **`repo-template/` is the home for installable diocese automation.** REPO-09 set the precedent; PUBLISH-06's handbook build + `sync-handbook.sh` followed it.

## Decisions made (in-sprint)

| Decision | Resolution | Notes |
|---|---|---|
| AI-13 "represented in the retention schedule" | **Match `category` against the bundle `classifications`** (by id/name, case-insensitive), not the free-text `retention_schedule` rows. | Per-policy matching against prose rows is unreliable in v0.1; classifications is the controlled vocabulary extraction already uses. Recorded in the AI-13 design doc; flagged for Chuck. |
| APP-09 clone/create timing | **Capture-only.** The screen validates + persists the repo choice; the actual clone/create + working-copy setup is deferred to wizard-completion provisioning (APP-15/16). | Deviates from the sprint-plan note ("Calls into GitHubProvider.clone + setup"); cloning mid-wizard is a destructive side effect on a back-navigable screen. Documented + flagged. |
| foundational-guard as a required check | **Stays advisory in v0.1**, documented as an optional per-diocese step in `HOWTO-GitHub-Team-Setup.md` (Part 3) with the path-filter caveat. | A naive required check + path-filtered workflow hangs non-policy PRs; the clean fix (drop the `paths:` filter) would change behavior for all future installs, which we avoided for v0.1. |
| APP-22 ticket-text accuracy | **Ticket corrected.** The parenthetical method list (clone/branch/commit/push/pull) was wrong; the real duplication was `_resolve_repo` across the 5 PR methods + push/pull. | Inline correction added to the ticket entry. |
| Node 24 action bump scope | **Bumped both** the shipped `repo-template` workflows and the live `pt-policy` copies; left the Astro build's `node-version: '20'` input alone (separate toolchain). | Live-confirmed on `pt-policy`. |

## Lane status (end of Week 4)

**Cross-Cutting (REPO):** REPO-09 (L2 guard) merged + live on `pt-policy`. REPO-10 (generic-ship audit) and REPO-11 (Python pin) are Week 5. REPO-08 (Team tier + branch protection) closed pre-Week-4.

**Ingest (P0.1):** INGEST-04 (manifest model) merged. INGEST-05 (incremental re-run) and INGEST-06 (full PT corpus = the 19 spike PDFs per OQ-08) are Week 5.

**AI (P0.2):** AI-07 (audit emitter), AI-12-revised (bundle read), AI-13 (gap detection) merged. AI-10 (inventory-pass orchestrator) consumes the audit emitter + manifest next.

**App (P0.3 + P0.4 + P0.6):** APP-20 (L1 gate), APP-08 (wizard skeleton), APP-09 (wizard screen 1), APP-22 (refactor) merged. APP-10..16 (remaining wizard screens) and APP-23 (read-only detail view + L1 gate) are Week 5.

**Publish (P0.5):** PUBLISH-06 (handbook build) merged + live on `pt-policy`. PUBLISH-07 (serve the artifact at `handbook.ptdiocese.org`) is Week 5.

## Risks and residuals

- **`foundational-guard` is advisory, not enforced, on `pt-policy`.** It runs and goes red on violations (proven), but is not a required check. Making it required cleanly needs the path-filter change; documented for the diocese to opt into.
- **The wizard does not provision yet.** APP-09 captures config only; nothing clones/creates a repo or commits wizard config. APP-15/16 close that. Until then, onboarding is not end-to-end.
- **Handbook is built but not served.** PUBLISH-06 uploads an artifact; PUBLISH-07 serves it. No public handbook URL until then.
- **`pt-policy` merges currently need an admin bypass.** The ruleset requires an approving review the PR author cannot self-supply; v0.1 merges via temporary bypass (restored after). A second reviewer or a standing admin-bypass entry would remove the friction; deferred as a per-diocese operational choice.

## Decisions waiting on Chuck

1. **PUBLISH-07 serving target** for Week 5 (`handbook.ptdiocese.org` DNS is Chuck-owned per OQ-06).
2. **Confirm Week-5 scope** (polish, wizard screens, install verification on a clean VM = the REPO-10 generic-ship test).

(The `foundational-guard` required-check question is already decided: advisory for v0.1, with the optional per-diocese enforcement step documented in `HOWTO-GitHub-Team-Setup.md` Part 3. Not waiting on anyone.)

## Week 5 plan preview

Polish week: PUBLISH-07 (serve the handbook at the real subdomain), the remaining wizard screens (APP-10..16) + provisioning (APP-15/16), APP-23 (read-only detail view), REPO-10 (generic-ship audit + clean-VM install verification), REPO-11 (Python pin), INGEST-05/06 (incremental re-run + full PT-corpus run), AI-10 (inventory-pass orchestrator). Hard scope freeze at end of Week 5 ahead of the mid-June DISC demo.
