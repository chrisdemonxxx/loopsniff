import { defineConfig } from "@playwright/test";

// Default to local; require an explicit env var to hit any remote env.
// This prevents `npx playwright test` from accidentally hammering production.
const localPort = process.env.ADMIN_E2E_PORT || "3000";
const localBaseURL =
  process.env.ADMIN_BASE_URL_LOCAL || `http://127.0.0.1:${localPort}`;

const env = (process.env.PW_ENV || "local").toLowerCase();
const baseURL =
  env === "production"
    ? process.env.ADMIN_BASE_URL_PROD || "https://admin.kliqboost.online"
    : env === "staging"
    ? process.env.ADMIN_BASE_URL_STAGING || localBaseURL
    : localBaseURL;

const startServer = process.env.PW_START_SERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  ...(startServer
    ? {
        webServer: {
          command: `npm run dev -- --port ${localPort}`,
          url: localBaseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }
    : {}),
  projects: [
    { name: "staging", use: { baseURL: process.env.ADMIN_BASE_URL_STAGING || baseURL } },
    {
      name: "production",
      use: { baseURL: process.env.ADMIN_BASE_URL_PROD || "https://admin.kliqboost.online" },
    },
    {
      name: "local",
      use: {
        baseURL: localBaseURL,
      },
    },
  ],
});
