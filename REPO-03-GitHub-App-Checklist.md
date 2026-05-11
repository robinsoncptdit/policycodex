# REPO-03: GitHub App Registration Checklist

**For:** Chuck (action item; ~15 minutes in the GitHub UI)
**Author:** Scarlet, Friday-night Phase 3 prep
**Reference ticket:** REPO-03 in `PolicyWonk-v0.1-Tickets.md`
**App live at:** <https://github.com/apps/policycodex> (public install URL; share with other dioceses for their installs)
**Owner-side settings:** <https://github.com/settings/apps/PolicyCodex> (Chuck-only)

## What this is

PolicyCodex authenticates to each diocese's GitHub.com organization via a GitHub App, not via personal access tokens. The App is registered once on the PolicyCodex side; each diocese installs that App on their org. This checklist is for the one-time PolicyCodex-side registration.

## Step-by-step

1. Navigate to https://github.com/settings/apps/new (or, if registering under an org, `https://github.com/organizations/<org>/settings/apps/new`).

2. Fill in the basic fields:

   | Field | Value |
   |---|---|
   | GitHub App name | `PolicyCodex` (or `PolicyCodex-dev` if `PolicyCodex` is taken; trademark check pending under OQ-02) |
   | Description | "Policy lifecycle management for Catholic dioceses. Reads and writes a private policy repo, opens PRs for edits, and triggers handbook builds." |
   | Homepage URL | Placeholder for now: `https://github.com/<your-account>/policycodex` (the public PolicyCodex repo, when it exists). Update post-launch. |
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
   | Issues | Read (optional; useful if PolicyCodex later adds issue-linking) |

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
   - Click "Generate a private key." A `.pem` file downloads. Save it as `~/.config/policycodex/github-app.pem` (create the directory if needed; `chmod 600` the file).
   - The App's **Client ID** appears on the same page. Save it.
   - Generate a **Client secret** if you want OAuth-style user-on-behalf-of flows. Save it.

8. Install the App on the PT GitHub org [`Diocese-of-Pensacola-Tallahassee`](https://github.com/Diocese-of-Pensacola-Tallahassee). Run REPO-04 first so the `pt-policy` repo exists, then:
   - From the App's settings page, click "Install App."
   - Select `Diocese-of-Pensacola-Tallahassee`, choose "Only select repositories" → `pt-policy` (least-privilege), and confirm.

## Outputs

**Credentials stay local.** App ID, Client ID, Client secret, and the `.pem` are stored under `~/.config/policycodex/` and **not** shared in chat. APP-04's `GitHubProvider` reads them at runtime from that directory (or from `POLICYCODEX_GH_*` environment variables for containerized deploys).

**Share with Scarlet in chat (non-secret only):**
- The exact registered App name (in case the OQ-02 trademark check forces a rename).
- Confirmation the App was created and the `.pem` is saved at `~/.config/policycodex/github-app.pem` (`chmod 600`).

**Expected files under `~/.config/policycodex/` after this checklist:**
- The downloaded `.pem` private key. Keep GitHub's original filename (e.g., `policycodex.YYYY-MM-DD.private-key.pem`) so the generation date is encoded in the name for rotation audits. **`chmod 600`.**
- `config.env` — plain text key/value pairs:
  ```
  POLICYCODEX_GH_APP_ID=<numeric app id>
  POLICYCODEX_GH_CLIENT_ID=<client id>
  POLICYCODEX_GH_CLIENT_SECRET=<client secret, if generated>
  POLICYCODEX_GH_APP_NAME=<exact app name>
  POLICYCODEX_GH_INSTALLATION_ID=<per-org install id, captured at install time>
  POLICYCODEX_GH_PRIVATE_KEY_PATH=<absolute path to the .pem file>
  ```
  **`chmod 600`.** Never committed; this directory is outside the repo. APP-04's `GitHubProvider` reads this file (or the equivalent env vars in containerized deploys) at startup.

## Notes

- Don't make this App "public" in the GitHub Marketplace sense yet. Public App listings have separate review processes; defer to v0.2.
- If trademark on "PolicyCodex" doesn't clear (OQ-02), register a temporary App name like `PolicyCodex-pt-pilot` and we'll re-register before DISC.
- The Apps API permits transferring ownership to a GitHub org later if you want the canonical PolicyCodex org to own the App.
