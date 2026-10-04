import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3101",
  },
  // Serves the production build; run `pnpm --filter web build` first.
  // With a dev server already on :3000 it reuses it instead.
  webServer: {
    command: "pnpm start --port 3101",
    url: "http://127.0.0.1:3101/login",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
  },
})
