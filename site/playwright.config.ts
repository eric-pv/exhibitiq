import { defineConfig, devices } from "@playwright/test";

// Runs against the production build served by `vite preview`.
// Browsers: uses PLAYWRIGHT_BROWSERS_PATH (preinstalled in the cloud workspace);
// in GitHub Actions run `npx playwright install chromium` first.
export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results",
  reporter: [["list"]],
  use: { baseURL: "http://localhost:4173", trace: "off" },
  webServer: {
    command: "npm run preview",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 820, height: 1180 }, hasTouch: true } },
  ],
});
