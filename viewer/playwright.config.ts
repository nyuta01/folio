import { defineConfig } from "@playwright/test";

/**
 * Playwright configuration for the Folio Viewer frontend smoke.
 *
 * This file is intentionally **not** wired into `make verify`. Run it
 * locally with:
 *
 *   cd viewer
 *   npm install
 *   npx playwright install --with-deps chromium
 *   FOLIO_SHEET=<path> npm run test:e2e
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "off",
    headless: true,
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
