import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30000,
  reporter: [["line"]],
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
  webServer: {
    command: "python3 -m http.server 4173 --bind 127.0.0.1 --directory ../..",
    port: 4173,
    reuseExistingServer: false,
  },
  use: {
    // WebKit on macOS returns `resource unavailable` for query URLs on the
    // numeric loopback origin, while `localhost` resolves to the same local
    // fixture server and supports those URLs reliably.
    baseURL: "http://localhost:4173",
    screenshot: "only-on-failure",
  },
});
