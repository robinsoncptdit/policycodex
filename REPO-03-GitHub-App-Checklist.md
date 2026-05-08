# REPO-03: GitHub App Registration Checklist

**For:** Chuck (action item; ~15 minutes in the GitHub UI)
**Author:** Scarlet, Friday-night Phase 3 prep
**Reference ticket:** REPO-03 in `PolicyWonk-v0.1-Tickets.md`

## What this is

PolicyWonk authenticates to each diocese's GitHub.com organization via a GitHub App, not via personal access tokens. The App is registered once on the PolicyWonk side; each diocese installs that App on their org. This checklist is for the one-time PolicyWonk-side registration.

## Step-by-step

1. Navigate to https://github.com/settings/apps/new (or, if registering under an org, `https://github.com/organizations/<org>/settings/apps/new`).

2. Fill in the basic fields:

   | Field | Value |
   |---|---|
   | GitHub App name | `PolicyWonk` (or `PolicyWonk-dev` if `PolicyWonk` is taken; trademark check pending under OQ-02) |
   | Description | "Policy lifecycle management for Catholic dioceses. Reads and writes a private policy repo, opens PRs for edits, and triggers handbook builds." |
   | Homepage URL | Placeholder for now: `https://github.com/<your-account>/policywonk` (the public PolicyWonk repo, when it exists). Update post-launch. |
   | Callback URL | `http://localhost:8080/auth/github/callback` for local dev. Add prod subdomain later. |
   | Setup URL | Optional. Leave blank for v0.1. |
   | Webhook URL | Optional for v0.1 (we can poll PR state via REST). Leave blank or use `http://localhost:8080/webhook/github` if you want to wire webhooks now. |
   | Webhook secret | Generate a random secret if you set the webhook URL. Save it. |

3. Permissions (Repository permissions):

   | Permission | Access |
   |---|---|
   | Contents | Read and write |
   | Pull requests | Read and write |
   | Metadata | Read (mandatory; auto-selected) |
   | Checks | Read |
   | Workflows | Read and write (needed to commit `.github/workflows/handbook.yml`) |
   | Administration | Read (needed to read branch protection rules) |
   | Issues | Read (optional; useful if PolicyWonk later adds issue-linking) |

   All other permissions: No access.

   Organization permissions: No access for v0.1.
   Account permissions: No access.

4. Subscribe to events (only if you set the webhook URL above):
   - Pull request
   - Pull request review
   - Push

5. Where can this GitHub App be installed?
   - **Any account** (so any diocese can install it on their own org)

6. Click "Create GitHub App."

7. On the next page:
   - Note the **App ID** (numeric). Save it.
   - Click "Generate a private key." A `.pem` file downloads. Save it as `~/.config/policywonk/github-app.pem` (create the directory if needed; `chmod 600` the file).
   - The App's **Client ID** appears on the same page. Save it.
   - Generate a **Client secret** if you want OAuth-style user-on-behalf-of flows. Save it.

8. Install the App on the PT GitHub org once it exists (REPO-04 prep doc covers org creation):
   - From the App's settings page, click "Install App."
   - Select the PT org, choose "All repositories" or just `pt-policy`, and confirm.

## Outputs to share with Scarlet

When done, share these in chat:
- App ID (numeric)
- Path to the `.pem` file (e.g., `~/.config/policywonk/github-app.pem`)
- Client ID
- Client secret (if generated)
- The exact App name (in case the trademark check forces a rename)

These wire into APP-04's `GitHubProvider` implementation in Week 2.

## Notes

- Don't make this App "public" in the GitHub Marketplace sense yet. Public App listings have separate review processes; defer to v0.2.
- If trademark on "PolicyWonk" doesn't clear (OQ-02), register a temporary App name like `PolicyWonk-pt-pilot` and we'll re-register before DISC.
- The Apps API permits transferring ownership to a GitHub org later if you want the canonical PolicyWonk org to own the App.
