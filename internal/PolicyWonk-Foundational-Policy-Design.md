# Foundational Policies as Data + Document

**Status:** Approved 2026-05-13 by Chuck via brainstorm. Lands as Week 3+ work; does not change Friday's sprint scope.

## Why this design exists

The Document Retention Policy is simultaneously two things:

1. A real policy in the diocese's inventory. It has an owner (the CFO), an effective date, a review cadence. It is reviewed and amended through the normal Drafted, Reviewed, Published gate flow. It is not infrastructure.
2. A source-of-truth reference document. Its contents define configuration variables the app consumes: the 8 top-level classifications and the ~150-row record-retention schedule.

The Git-backed architecture already handles role 1 cleanly. The remaining design problem is role 2: when the CFO amends the retention policy, how do dependent app variables update? And what prevents a well-meaning admin from deleting a file that 50 other things depend on?

This document answers those questions for v0.1.

## Architecture

### Policy-bundle directory pattern

Data-bearing policies live in their own subdirectory under `policies/`. Non-data-bearing policies stay flat as plain markdown files. The bundle pattern is opt-in via a frontmatter flag.

```
policies/
  document-retention/         <- data-bearing: lives in a bundle
    policy.md                 <- narrative (intro, scope, definitions)
    data.yaml                 <- canonical machine-readable variables
    source.pdf                <- optional archival copy of the original
  internal-controls.md        <- regular: flat markdown file
  whistleblower.md            <- regular: flat markdown file
```

### Source-of-truth rules

- `data.yaml` is canonical for machine-readable variables. The app reads it directly; no markdown parsing.
- `policy.md` is canonical for narrative. Its frontmatter declares the bundle's role.
- Both files are reviewed in the same PR. They cannot diverge across a publish event.

### Frontmatter on policy.md

```yaml
---
title: Document Retention Policy
owner: CFO
foundational: true                          # marks this as a bundle
provides:                                   # capabilities the bundle delivers
  - classifications
  - retention-schedule
effective_date: 2022-08-01
last_review: 2022-08-01
retention_period: Permanent
---
```

`foundational: true` tells the app to apply the four-layer deletion protection (below). `provides:` lists the capabilities the bundle delivers, so the app can validate that every capability it needs is satisfied by some published foundational policy at startup.

## data.yaml schema (v0.1)

```yaml
# Section 3.0 of the source policy — 8 top-level data classifications
classifications:
  - id: administrative                  # stable slug; inventory policies reference by id
    name: Administrative                # display name in the UI picker
    # optional: description, deprecated: true (for soft-delete)
  - id: personnel
    name: Personnel
  - id: financial
    name: Financial
  - id: legal
    name: Legal
  - id: property
    name: Property
  - id: cemetery
    name: Cemetery
  - id: publications
    name: Publications
  - id: sacramental
    name: Sacramental

# Appendix A — the record retention schedule
retention_schedule:
  - group: Administrative Records (ALL Departments)
    type: "Administrative Records — records that document routine activities"
    retention: 2 years                  # free-text string in v0.1
    medium: Paper/Elec
    retained_at: On-site/Off-site
    # optional: sub_group, notes, disposal
  - group: Catholic Schools Office
    sub_group: TCCED
    type: School Self-Study Document
    retention: Permanent
    medium: Paper
    retained_at: On-site/Off-site/School
  # ... ~150 rows total
```

### Schema notes

- Classifications (Section 3.0) and retention-schedule groups (Appendix A) are two independent axes in v0.1, not parent/child. The AI prompt sees both. A future v0.2 may add a `classification:` cross-reference on each retention row if you decide they need to be linked.
- Retention is a free-text string in v0.1. Real values are messy: Permanent, 7 years, Termination + 4 years, Until superseded, Sale + 7 years, Death of student. Free text is fine for AI context injection. v0.2 may add a structured form when the app needs to compute auto-destruction dates.
- `id` on a classification is the stable reference. Renaming the display name is safe; changing the id is a hard remove and requires re-classifying dependent policies first.

## Lifecycle (live sync)

```
CFO edits via app UI (typed tables)
  -> App generates YAML diff
  -> App commits + opens PR  (Drafted gate)
  -> Reviewer approves in app  (Reviewed gate)
  -> Publisher merges in app  (Published gate)
    +-> Handbook rebuilds  (PUBLISH-06 Action on push to main)
    +-> App's local working copy pulls  (APP-05 polling cadence, ~5 min)
    +-> App reads new data.yaml on next request  (no cache in v0.1)
    +-> Next AI extraction injects new taxonomy + retention schedule
```

Effective sync latency equals the APP-05 polling cadence (≈5 min). A GitHub-webhook-based push is a v0.2 optimization, not v0.1 scope.

No in-memory cache for data.yaml in v0.1. The file is small enough that reading on every request is acceptable. Adding mtime-based caching is a v0.2 optimization if any real diocese experiences latency.

## Change semantics

| What changed | Existing inventory effect | App response |
|---|---|---|
| Add classification | None | Available for new classifications immediately |
| Remove classification | Policies referencing the id would be orphaned | **Soft-delete only.** Sets `deprecated: true`. The id remains in `data.yaml`. UI hides the deprecated classification from the picker for new policies but keeps it valid for existing references. Hard remove requires re-classifying dependent policies first; app UI blocks, CI blocks if someone bypasses the UI. |
| Rename classification (display name only) | None | UI shows new name; `id` is the stable reference |
| Add retention row | None | Available as AI prompt context immediately |
| Remove retention row | None | AI no longer sees that row as context; existing policy retention values are unchanged |
| Change retention period | None (retention is a per-policy snapshot at extraction time) | New AI suggestions use the new value. Optional: app shows a "re-review N policies under old value" banner |

**No auto-re-extraction** of inventory policies after a taxonomy change in v0.1. Admin manually triggers per policy ("re-classify with AI" action). v0.2 may add a bulk re-extraction action.

## Deletion protection: four layers

| Layer | Mechanism | v0.1 ownership |
|---|---|---|
| L0 | Git branch protection on the policy repo | Already planned (REPO-04 / REPO-08) |
| L1 | App UI hides or disables the Delete button for any policy with `foundational: true` in its frontmatter | New APP ticket (Week 3) |
| L2 | Pre-merge CI check: PR diff cannot remove a `foundational: true` file or empty a declared `provides:` capability | New REPO ticket (Week 3-4) |
| L3 | App startup self-check: every required `provides:` capability is satisfied by some published foundational policy with valid `data.yaml`. Otherwise the app refuses to start and shows a clear error pointing back to the policy repo. | New APP ticket (Week 3) |

To actually destroy the retention policy, a malicious or confused admin would have to bypass the app UI, bypass branch protection, and override the CI block. Even then, the app refuses to operate and surfaces exactly what's missing.

## Onboarding (deferred to APP-15-revised)

A new diocese onboards via the seven-screen wizard. Screen 7 (source-of-truth reference documents) gets the heaviest behavior change:

1. The admin uploads the diocese's retention policy as a PDF.
2. The app runs AI extraction against the PDF (using INGEST-03 + the AI provider) to produce a draft `data.yaml`.
3. The admin reviews the draft inline (typed tables for classifications and retention rows).
4. On confirm, the app scaffolds `policies/document-retention/` as a bundle: writes `policy.md` (initial narrative converted from the PDF), `data.yaml` (confirmed), and `source.pdf` (archived original). Marks `foundational: true` in `policy.md` frontmatter with `provides: [classifications, retention-schedule]`.
5. The app commits the bundle directly to `main` as the initial scaffold (no PR for the bootstrap, since there's no prior state to review against).

After onboarding, all subsequent edits go through the normal Drafted, Reviewed, Published gate flow.

## Implications for the v0.1 plan

### Friday 2026-05-15 sprint (no scope change)

- **AI-11** still ships Friday at size S. The taxonomy injection reads from `ai/taxonomies/pt_classification.yaml`, a seed file that uses the `data.yaml` schema above. When the bundle scaffolding lands in Week 3, the file moves to `policies/document-retention/data.yaml`. The injection code is identical either way (`yaml.safe_load(path)` plus template substitution).
- **AI-05, INGEST-03, APP-02, AI-08** unchanged.

### Week 3+ new and revised tickets

| Ticket | Scope | Size | Week |
|---|---|---|---|
| APP-XX | Foundational frontmatter recognition + L1 UI gate (hide Delete on `foundational: true` policies) | S | 3 |
| APP-YY | App startup self-check (L3): every required `provides:` capability is satisfied | S | 3 |
| REPO-XX | CI guard (L2) on policy repo: block PRs that remove foundational files or empty a `provides:` | S | 3-4 |
| INGEST-XX | Bundle-aware reader: when `policies/<slug>/` contains `policy.md` + `data.yaml`, treat the directory as one logical policy in the inventory | S | 3 |
| AI-12-revised | Wire AI extraction to read `policies/document-retention/data.yaml` from the local working copy (replaces "hardcoded path to PT retention PDF"). Shrinks from M to S. | S | 3 |
| APP-15-revised | Wizard screen 7: upload retention PDF, AI-extract to draft `data.yaml`, scaffold the bundle as the first foundational policy. | M | 4 |

These tickets need to be folded into `PolicyWonk-v0.1-Tickets.md` before Week 3 sprint planning.

## What this design intentionally does not do

- **It does not link classifications to retention rows.** v0.2 may add a `classification:` field on each retention row if you decide they need to be cross-referenced.
- **It does not parse retention as structured data.** Retention stays free-text in v0.1. v0.2 may add `{years, trigger, offset_years}` when the app needs to compute auto-destruction.
- **It does not implement webhook-based push from GitHub.** APP-05's polling cadence (~5 min) is the sync mechanism. v0.2 may add webhooks if latency becomes a problem.
- **It does not auto-re-extract inventory policies after a taxonomy change.** Admin manually triggers per policy. v0.2 may add a bulk action.
- **It does not generalize beyond a single foundational document for v0.1.** PT has one (the retention policy). The architecture supports more, but no second foundational document is planned for v0.1.
