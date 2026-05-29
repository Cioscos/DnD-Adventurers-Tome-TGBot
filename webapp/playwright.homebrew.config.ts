import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e-playwright/homebrew",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  expect: {
    timeout: 5000,
  },
  reporter: "list",
  use: {
    trace: "on-first-retry",
  },
});
