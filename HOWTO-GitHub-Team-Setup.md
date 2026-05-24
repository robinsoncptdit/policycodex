# How To: Set Up GitHub Team Tier and Branch Protection

PolicyCodex stores every policy as a markdown file in a private GitHub repo your
organization owns. The audit trail (every change reviewed, approved, and merged
through a pull request) depends on **branch protection** being enforced on that
repo's `main` branch.

GitHub does not enforce branch protection or rulesets on **private** repositories
in a **Free** organization. To get an enforceable audit trail, upgrade your
organization to the **Team** plan first, then turn on the ruleset.

This guide walks both steps. It takes about 15 minutes. You need the **Owner**
role on the organization.

## What you need first

- Owner access to the GitHub organization that holds your policy repo.
- A payment method (the Team plan is billed per seat).
- The name of your policy repo (the private repo PolicyCodex commits to).

## Part 1: Upgrade the organization to the Team plan

1. Go to your organization on GitHub: `https://github.com/<your-org>`.
2. Open **Settings** (you must be an org Owner to see org settings).
3. In the left sidebar, open **Billing and plans**, then **Plans and usage**.
4. Find **Current plan** and choose **Upgrade**.
5. Select the **Team** plan and continue to checkout.
6. Set the number of paid seats. Team bills per member, so this is the seat count
   you want to pay for. Approximately $4 per user per month at time of writing;
   confirm current pricing at `https://github.com/pricing`.
7. Choose the billing cycle (monthly or yearly), confirm the payment method, and
   complete the purchase.

When this finishes, the org's plan reads **Team** under Billing.

## Part 2: Turn on branch protection for your policy repo

With the org on Team, enforcement on a private repo now takes effect.

1. Go to your policy repo: `https://github.com/<your-org>/<your-repo>`.
2. Open **Settings**, then **Rules**, then **Rulesets**.
3. Create a new branch ruleset (or edit the one PolicyCodex onboarding created).
4. Set **Enforcement status** to **Active**.
5. Under **Target branches**, add your default branch: **`main`**.
6. Enable these rules (the audit-trail baseline):

   | Rule | Setting |
   |---|---|
   | Require a pull request before merging | On |
   | Required approvals | 1 |
   | Dismiss stale approvals when new commits are pushed | On |
   | Require conversation resolution before merging | On |
   | Require linear history | On |
   | Block force pushes | On |
   | Restrict deletions | On |
   | Include administrators (no bypass) | On |

7. Save the ruleset.

Add the `handbook-build` status check as required once your publish workflow
(the GitHub Actions handbook build) is in place. Leave it off until then so the
check does not block merges.

## Verify it works

1. On the policy repo, try to push a commit directly to `main`. It should be
   rejected; changes must go through a pull request.
2. Open a test pull request. Confirm it requires one approval before the merge
   button is enabled.
3. Delete the test branch after merging.

If a direct push to `main` still succeeds, the plan upgrade or the ruleset
enforcement did not take. Recheck that the org plan reads **Team** and that the
ruleset **Enforcement status** is **Active** with `main` listed as a target.

## Your values

Fill these in for your organization:

| Field | Value |
|---|---|
| Organization | `<your-org>` |
| Policy repo | `<your-repo>` |
| Seats purchased | |
| Plan enabled on (date) | |
| Ruleset enforcement Active? | |

## Why this matters

Branch protection plus required pull requests is the entire audit mechanism:
every policy change is traceable to a commit with a named approver, and nobody,
including org Owners, can bypass review. Do not relax the force-push, deletion,
or required-PR rules without accepting that you weaken the audit trail.
