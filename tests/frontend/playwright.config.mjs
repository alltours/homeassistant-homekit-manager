import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 15000,
  reporter: [["line"]],
  webServer: {
    command: "/Users/felixalshut/Documents/ChatGPT/Homeassistant/.venv-ha-2026.10.4/bin/python -m http.server 4173 --directory /Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager",
    port: 4173,
    reuseExistingServer: false,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    screenshot: "only-on-failure",
  },
});
