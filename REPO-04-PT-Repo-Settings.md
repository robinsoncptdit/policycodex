# REPO-04: PT Diocesan Policy Repo Settings

**For:** Chuck (action item; ~10 minutes in the GitHub UI, after PT GitHub org exists per OQ-07)
**Author:** Scarlet, Friday-night Phase 3 prep
**Reference ticket:** REPO-04 in `PolicyWonk-v0.1-Tickets.md`

## What this is

The PT diocese's policy repo. **Separate** from the public PolicyWonk app repo. Contains PT's actual policies as markdown. PolicyWonk-the-app talks to it via the GitHub App from REPO-03.

## Step-by-step

1. Confirm the PT GitHub organization name (OQ-07). Suggested: `diocesept` or `pensacola-tallahassee-diocese`. Whichever PT IT prefers.

2. Create the repo:

   | Field | Value |
   |---|---|
   | Owner | `<pt-org>` (the PT diocesan GitHub org) |
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
   Diocese of Pensacola-Tallahassee. It is managed by PolicyWonk
   (https://github.com/<polciywonk-org>/policywonk) on behalf of the
   diocesan IT and Document Control teams.

   - `policies/` — markdown files, one per policy, with YAML front matter.
   - `references/` — source-of-truth reference documents (e.g., the
     diocesan retention policy) used by PolicyWonk's AI extraction.
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

6. Install the PolicyWonk GitHub App on this org (per REPO-03 step 8). Restrict the App to just `pt-policy` if PT prefers least-privilege.

7. Add the PolicyWonk maintainer (Chuck's GitHub account, for now) as a collaborator with **Maintain** role for the v0.1 sprint. Reduce to **Triage** post-launch.

## Outputs to share with Scarlet

When done, share in chat:
- The full repo URL: `https://github.com/<pt-org>/pt-policy`
- The org name (whether `diocesept`, `pensacola-tallahassee-diocese`, or other)
- Confirmation that the GitHub App is installed on the org and scoped to `pt-policy`
- The handbook subdomain PT plans to use (Week 4 dependency, OQ-06; useful to know now even if the DNS isn't live)

## Notes

- Branch protection blocking force pushes plus required PRs is the entire audit trail for PRD G3 ("every policy change is auditable down to the commit, with a named approver"). Don't relax these without flagging the audit consequence.
- The `references/` directory is the source-of-truth for AI-12 (retention reference grounding). Drop the diocesan retention policy in there during onboarding.
- Don't enable Discussions, Pages, Projects, or Wiki on this repo. The handbook is published from a separate static-site build.
