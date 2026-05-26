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

## Part 3 (optional): Require the foundational-policy guard

PolicyCodex installs a `foundational-guard` GitHub Action in your policy repo
(from the repo template). On a pull request that changes `policies/`, it fails
the check if the diff deletes a foundational policy or empties a foundational
policy's `provides:` list. By default this check is **advisory**: it shows a red
mark on the pull request but does not block the merge.

To make it **blocking**, add it as a required status check:

1. On the policy repo, open **Settings**, then **Rules**, then your `main`
   ruleset.
2. Enable **Require status checks to pass**, then add the check named
   **`foundational-guard`**.
3. Save the ruleset.

**Caveat, read before you do this.** The guard's workflow only runs on pull
requests that change `policies/`. If you require the check while it still only
runs on `policies/` changes, then any pull request that does **not** touch
`policies/` (for example a docs or workflow change) will wait forever on a check
that never reports, and you will not be able to merge it. Two ways to avoid that:

- Only require the check if you accept that limitation, **or**
- Before requiring it, edit your copy of
  `.github/workflows/foundational-guard.yml` and remove the `paths:` filter so
  the guard runs on every pull request. The guard passes automatically when no
  policy file changed, so non-policy pull requests stay unblocked. Then add the
  required check.

PolicyCodex ships the guard advisory by default; requiring it is your choice.

## Part 4: Publish the handbook at a public custom subdomain

PolicyCodex builds your handbook on every merge to `main` (the build runs from `.github/workflows/build-handbook.yml`, vendored from the repo template). Once you complete this part, every merge also publishes the handbook to a public subdomain you control, served by GitHub Pages with HTTPS via Let's Encrypt. Cost is zero on the Team plan or higher.

Pages publishing from a private repo requires the Team plan or higher. Access-restricted ("private") Pages requires Enterprise Cloud and is out of scope for v0.1.

You need DNS control of the parent zone of your chosen subdomain. For example, to publish at `handbook.example.org`, you must be able to add CNAME and TXT records under `example.org`.

1. **Verify your apex domain at the org level (one-time, recommended).** This locks every subdomain at your apex (`*.example.org`) to your GitHub org, so no one else can stand up a `*.example.org` Pages site on a different account. On GitHub, open your org's **Settings**, then **Pages**, then **Add a domain**, and enter your apex (`example.org`, not `handbook.example.org`). GitHub shows you a TXT record. Add it to your DNS at the name `_github-pages-challenge-<your-org>.example.org` with the value GitHub provides. Verify propagation with `dig +short TXT _github-pages-challenge-<your-org>.example.org`. Back in GitHub, click **Verify**. Leave the TXT record in place; removing it un-verifies the apex.

2. **Create the subdomain CNAME.** In your DNS provider, add a CNAME record: name `handbook` (resolving to `handbook.example.org`), value `<your-org>.github.io` (your GitHub org name only, no repo name). Wait for DNS to propagate (a few minutes to a few hours). Verify with `dig +short CNAME handbook.example.org`; it should return `<your-org>.github.io.`.

3. **Enable Pages on the policy repo.** Open your policy repo's **Settings**, then **Pages**. Under **Build and deployment**, set **Source** to **GitHub Actions** (not "Deploy from a branch"). Under **Custom domain**, enter `handbook.example.org` and **Save**. GitHub runs a DNS check; wait for the green check (usually under a minute, once Step 2 has propagated). Do NOT commit a `CNAME` file to your repo; with the Actions source, the custom domain lives in Settings only.

4. **Trigger a deploy.** Push any commit to `main` (or re-run the latest **Build handbook** workflow from the Actions tab). The workflow now has three jobs: `preflight` checks the Pages configuration, `build` builds the handbook with your custom domain set as the canonical site URL, and `deploy` publishes to Pages. All three should go green. The `deploy` job summary shows the live URL. Visit it and confirm the handbook loads.

5. **Enforce HTTPS.** After Let's Encrypt provisions a certificate for your subdomain (this can take up to 24 hours from when DNS first resolved correctly), GitHub makes an **Enforce HTTPS** checkbox available in **Settings**, **Pages**. Enable it. From that point, plain-HTTP requests automatically redirect to HTTPS.

If the `deploy` job is gray rather than green, Pages is not yet enabled on the repo; complete Step 3. The `preflight` step intentionally swallows errors from the GitHub Pages API so a fresh repo without Pages does not red-flag its first merges; if `preflight` itself logs a non-200 response and you have already completed Step 3, check the workflow run for an auth or network problem with the `gh api` call. If the `deploy` job is red, open its log; the most common causes are a mismatch between the CNAME target and your GitHub org name (the target uses the org name only, not the repo path), or DNS that has not yet propagated. If the **Enforce HTTPS** checkbox is missing, Let's Encrypt has not provisioned yet; come back later. If you accidentally remove the `_github-pages-challenge-<your-org>` TXT record, re-add it from your org's Settings, Pages page; the apex stays verified for a grace period.

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
