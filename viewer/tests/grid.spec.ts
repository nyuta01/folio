import { expect, test } from "@playwright/test";

/**
 * Lightweight frontend smoke for Phase 5 V1+V4.
 *
 * Assumes a `folio-viewer serve <FOLIO_SHEET>` backend is reachable
 * at http://127.0.0.1:3000 (Vite proxies /api there) — the harness
 * documentation in `viewer/README.md` covers the full workflow.
 */

test("records grid shows type chips", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("records-table")).toBeVisible();
  // V1 type chips render alongside column names.
  await expect(page.getByText(/STRING|INTEGER|NUMBER|BOOLEAN/i).first()).toBeVisible();
});

test("dashboard tab renders the materialize button", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("tab-dashboard").click();
  await expect(page.getByTestId("dashboard")).toBeVisible();
  await expect(page.getByTestId("materialize-all")).toBeVisible();
});
