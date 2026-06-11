"""DISC-16: end-to-end smoke. Drives the wizard from /admin-account/ to /catalog/.

Run:
  python tests/disc_smoke/playwright_smoke.py

Required env vars (set in GitHub Actions repo settings):
  DISC_SMOKE_GH_APP_ID, DISC_SMOKE_GH_INSTALLATION_ID,
  DISC_SMOKE_GH_PRIVATE_KEY, DISC_SMOKE_ANTHROPIC_KEY,
  DISC_SMOKE_TEST_ORG
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("POLICYCODEX_BASE_URL", "http://localhost:8000")
CORPUS = Path(__file__).parent.parent / "fixtures" / "disc-smoke-corpus"

# Required CI secrets (set in GitHub Actions repo settings):
GH_APP_ID = os.environ["DISC_SMOKE_GH_APP_ID"]
GH_INSTALLATION_ID = os.environ["DISC_SMOKE_GH_INSTALLATION_ID"]
GH_PEM = os.environ["DISC_SMOKE_GH_PRIVATE_KEY"]
ANTHROPIC_KEY = os.environ["DISC_SMOKE_ANTHROPIC_KEY"]
TEST_ORG = os.environ["DISC_SMOKE_TEST_ORG"]
REPO_NAME = f"disc-smoke-{os.environ.get('GITHUB_SHA', 'local')[:7]}"


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # -- Screen 1: admin-account ----------------------------------------
        page.goto(f"{BASE}/onboarding/admin-account/")
        page.fill('input[name="username"]', "disc-admin")
        page.fill('input[name="email"]', "disc@smoke.test")
        page.fill('input[name="password"]', "smoke-test-password-9")
        page.fill('input[name="password_confirm"]', "smoke-test-password-9")
        page.click('button[name="action"][value="continue"]')

        # -- Screen 2: github-app -------------------------------------------
        expect(page).to_have_url(f"{BASE}/onboarding/github-app/", timeout=10_000)
        page.fill('input[name="app_id"]', GH_APP_ID)
        page.fill('input[name="installation_id"]', GH_INSTALLATION_ID)
        page.fill('textarea[name="private_key_pem"]', GH_PEM)
        # HTMX-driven test; click the HTMX button and wait for the ok fragment.
        page.click('button:has-text("Test connection")')
        expect(page.locator('[data-state="ok"]')).to_be_visible(timeout=15_000)
        page.click('button[name="action"][value="continue"]')

        # -- Screen 3: llm-provider -----------------------------------------
        expect(page).to_have_url(f"{BASE}/onboarding/llm-provider/", timeout=10_000)
        page.check('input[name="provider"][value="claude"]')
        page.fill('input[name="api_key"]', ANTHROPIC_KEY)
        page.click('button:has-text("Test key")')
        expect(page.locator('[data-state="ok"]')).to_be_visible(timeout=15_000)
        page.click('button[name="action"][value="continue"]')

        # -- Screen 4: github-repo ------------------------------------------
        expect(page).to_have_url(f"{BASE}/onboarding/github-repo/", timeout=10_000)
        page.check('input[name="mode"][value="create"]')
        page.fill('input[name="org"]', TEST_ORG)
        page.fill('input[name="repo_name"]', REPO_NAME)
        # Branch field defaults to "main"; leave it.
        page.click('button[name="action"][value="continue"]')

        # -- Screen 5: configuration (accept defaults) ----------------------
        expect(page).to_have_url(f"{BASE}/onboarding/configuration/", timeout=30_000)
        page.click('button[name="action"][value="continue"]')

        # -- Screen 6: retention-policy (HTMX-driven) -----------------------
        # The wizard may land on retention-policy upload or review depending on
        # wizard state. Land on the upload path first.
        expect(page).to_have_url(f"{BASE}/onboarding/retention-policy/", timeout=10_000)
        # The PDF input is inside the HTMX-rendered #screen7-body fragment.
        # Locate it inside the form.
        page.set_input_files('input[type="file"]', str(CORPUS / "00-retention-policy.pdf"))
        # Click "Upload and extract" (hx-post triggers the fragment swap).
        page.click('button[name="action"][value="extract"]')
        # Wait for review mode: "Review the extracted data" text appears.
        expect(page.locator("text=Review the extracted")).to_be_visible(timeout=90_000)
        # Click "Accept and scaffold".
        page.click('button[name="action"][value="accept"]')

        # -- Screen 7: policy-documents -------------------------------------
        expect(page).to_have_url(f"{BASE}/onboarding/policy-documents/", timeout=10_000)
        other_pdfs = sorted(str(f) for f in CORPUS.glob("*.pdf") if not f.name.startswith("00-"))
        page.set_input_files('input[name="files"]', other_pdfs)
        page.click('button[name="action"][value="continue"]')

        # -- Inventory page (HTMX polling, auto-redirect to /catalog/) ------
        expect(page).to_have_url(f"{BASE}/onboarding/inventory/", timeout=10_000)
        # The inventory page polls every 2 s; when all items complete the
        # HTMX status endpoint returns HX-Redirect: /catalog/ which HTMX
        # sets as window.location. Allow up to 10 min.
        expect(page).to_have_url(f"{BASE}/catalog/", timeout=600_000)

        # -- Catalog assertion ----------------------------------------------
        # The catalog renders policies as <tr> rows inside a <tbody>.
        # Each row corresponds to one policy (18 text PDFs + 1 foundational
        # retention bundle = 19 total; the image-only PDF may fail extraction).
        # Assert >= 17 rows (allows 1 image-only skip + 1 spare).
        row_count = page.locator("table tbody tr").count()
        assert row_count >= 17, (
            f"Catalog has only {row_count} policy rows; expected >= 17. "
            "Check inventory logs for extraction failures."
        )

        browser.close()

    print(f"DISC SMOKE PASS — {row_count} catalog rows")


if __name__ == "__main__":
    run()
