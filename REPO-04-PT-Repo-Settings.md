# REPO-04: PT Diocesan Policy Repo Settings

**For:** Chuck (action item; ~10 minutes in the GitHub UI)
**PT GitHub org:** [`Diocese-of-Pensacola-Tallahassee`](https://github.com/Diocese-of-Pensacola-Tallahassee) (OQ-07 resolved 2026-05-11)
**Author:** Scarlet, Friday-night Phase 3 prep
**Reference ticket:** REPO-04 in `PolicyWonk-v0.1-Tickets.md`

## Status (2026-05-11): partial; only OQ-10 remains

Done:
- `pt-policy` exists on `Diocese-of-Pensacola-Tallahassee` (private, `main` default).
- Ruleset on `main` configured per the rule choices in step 3.
- Initial README + `policies/.gitkeep` + `references/.gitkeep` + `.github/.gitkeep` committed.
- PolicyCodex GitHub App installed on the org, scoped to `pt-policy` (step 6).
- Step 7 (collaborator add) not applicable — Chuck is an Owner of the org.

Remaining (all gated on **OQ-10**, the Free → Team upgrade, currently deferred):
1. Enforcement status: Disabled → Active.
2. Target branches: add `main`.
3. Underlying upgrade: GitHub Free → Team so (1) takes effect.

App-lane work against `pt-policy` (clone, branch, commit, push, open PR) functions today without enforcement. Branch protection is the audit-trail mechanism for PRD G3; it needs to be enforcing before week 4 lane acceptance, not before APP-04 starts.

## What this is

The PT diocese's policy repo. **Separate** from the public PolicyCodex app repo. Contains PT's actual policies as markdown. PolicyCodex-the-app talks to it via the GitHub App from REPO-03.

## Step-by-step

1. Create the repo under [`Diocese-of-Pensacola-Tallahassee`](https://github.com/Diocese-of-Pensacola-Tallahassee):

   | Field | Value |
   |---|---|
   | Owner | `Diocese-of-Pensacola-Tallahassee` |
   | Repository name | `pt-policy` |
   | Visibility | **Private** |
   | Initialize with README | yes (we overwrite the contents in step 4) |
   | Default branch | `main` |
   | License | None (the repo holds proprietary policy content; this repo's contents are not open-source) |
   | .gitignore | None |

3. Configure branch protection on `main` (Settings → Branches → Add rule):

   | Setting | Value |
   |---|---|
   | Branch name pattern | `main` |
   | Require a pull request before merging | yes |
   | Require approvals | **1** |
   | Dismiss stale pull request approvals when new commits are pushed | yes |
   | Require review from Code Owners | optional (skip for v0.1; revisit when CODEOWNERS file ships in Week 3) |
   | Require status checks to pass before merging | yes (add the `handbook-build` check once PUBLISH-06 lands; for now this can stay off) |
   | Require branches to be up to date before merging | yes |
   | Require conversation resolution before merging | yes |
   | Require signed commits | optional. Recommend yes for the audit-trail goal in PRD G3. |
   | Require linear history | yes |
   | Include administrators | yes (so even Chuck can't bypass; everything goes through PR) |
   | Allow force pushes | no |
   | Allow deletions | no |

4. Replace the auto-generated README with this content (commit directly to `main` once, then branch protection takes over):

   ```markdown
   # PT Diocesan Policy Repo

   This repository holds the active policies, procedures, and by-laws for the
   Diocese of Pensacola-Tallahassee. It is managed by PolicyCodex
   (https://github.com/<policycodex-org>/policycodex) on behalf of the
   diocesan IT and Document Control teams.

   - `policies/` — markdown files, one per policy, with YAML front matter.
   - `references/` — source-of-truth reference documents (e.g., the
     diocesan retention policy) used by PolicyCodex's AI extraction.
   - `.github/workflows/` — GitHub Actions workflow that builds and
     deploys the public handbook on every merge to `main`.

   Edits land via pull requests. Drafts open as PRs; reviews approve them;
   merges publish them.

   For questions about a specific policy, contact the listed owner in
   the policy's YAML front matter.
   ```

5. Create the directory structure (commit on `main` with the README replacement):
   - `policies/.gitkeep` — empty file
   - `references/.gitkeep` — empty file
   - `.github/.gitkeep` — empty file (workflows land in PUBLISH-06)

6. Install the PolicyCodex GitHub App on this org. Public App URL: <https://github.com/apps/policycodex>. Click **Install** → pick `Diocese-of-Pensacola-Tallahassee` → choose **Only select repositories** → `pt-policy` (least-privilege) → confirm. Capture the Installation ID into `~/.config/policycodex/config.env` as `POLICYCODEX_GH_INSTALLATION_ID=<id>`; APP-04 needs it. (The ID appears in the install's settings URL: `https://github.com/organizations/Diocese-of-Pensacola-Tallahassee/settings/installations/<id>`.)

7. **Not applicable for v0.1.** Chuck is an Owner of `Diocese-of-Pensacola-Tallahassee` (confirmed 2026-05-11), so he already has Admin on every repo in the org. No collaborator add is needed. Revisit if maintainership transfers to a non-Owner contributor later.

## Outputs to share with Scarlet

When done, share in chat:
- Confirmation that the repo was created at `https://github.com/Diocese-of-Pensacola-Tallahassee/pt-policy`
- Confirmation that the GitHub App is installed on the org and scoped to `pt-policy`
- The handbook subdomain PT plans to use (Week 4 dependency, OQ-06; useful to know now even if the DNS isn't live)

## Notes

- Branch protection blocking force pushes plus required PRs is the entire audit trail for PRD G3 ("every policy change is auditable down to the commit, with a named approver"). Don't relax these without flagging the audit consequence.
- The `references/` directory is the source-of-truth for AI-12 (retention reference grounding). Drop the diocesan retention policy in there during onboarding.
- Don't enable Discussions, Pages, Projects, or Wiki on this repo. The handbook is published from a separate static-site build.
