import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const root = resolve(__dirname, "../..");
const python =
  process.env.AGENTREPLAY_TEST_PYTHON ||
  (process.platform === "win32"
    ? resolve(root, ".venv/Scripts/python.exe")
    : "python");
const data = mkdtempSync(resolve(tmpdir(), "agentreplay-e2e-"));
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:3011",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn agentreplay_api.main:app --host 127.0.0.1 --port 8011`,
      cwd: root,
      url: "http://127.0.0.1:8011/health",
      env: {
        AGENTREPLAY_DATABASE_URL: `sqlite:///${data.replaceAll("\\", "/")}/e2e.db`,
        AGENTREPLAY_API_KEY: "",
      },
      reuseExistingServer: false,
    },
    {
      command: "npm run start -- --port 3011",
      url: "http://127.0.0.1:3011",
      env: {
        AGENTREPLAY_BACKEND_URL: "http://127.0.0.1:8011",
        AGENTREPLAY_API_KEY: "",
      },
      reuseExistingServer: false,
    },
  ],
});
