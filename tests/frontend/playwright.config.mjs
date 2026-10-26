import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 15000,
  reporter: [["line"]],
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
  webServer: {
    command: "python3 -m http.server 4173 --directory ../..",
    port: 4173,
    reuseExistingServer: false,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    screenshot: "only-on-failure",
  },
});
