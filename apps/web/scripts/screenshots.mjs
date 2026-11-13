// Capture the real local application with synthetic demo data for the README.
// Start the API and production web server first; this creates real demo runs.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const base = process.env.AGENTREPLAY_SCREENSHOT_URL || "http://127.0.0.1:3000";
const directory = fileURLToPath(
  new URL("../../../docs/screenshots/", import.meta.url),
);
await mkdir(directory, { recursive: true });
const runs = [];
for (const fail of [false, false, true, false, true]) {
  const response = await fetch(`${base}/api/v1/demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request: "Find a mechanical keyboard under $100",
      fail,
    }),
  });
  if (!response.ok) throw new Error(`Demo API returned ${response.status}`);
  runs.push(await response.json());
}
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1040 },
    deviceScaleFactor: 1,
    locale: "en-US",
    timezoneId: "UTC",
  });
  await page.goto(base);
  await page.locator("tbody tr").first().waitFor();
  await page.screenshot({ path: `${directory}/dashboard.png`, fullPage: true });
  await page.goto(`${base}/?run=${runs[4].id}`);
  await page.getByRole("heading", { name: "Execution timeline" }).waitFor();
  await page.getByRole("tab", { name: "error" }).click();
  await page.screenshot({ path: `${directory}/execution.png`, fullPage: true });
  await page.goto(`${base}/?left=${runs[3].id}&right=${runs[4].id}`);
  await page.getByRole("heading", { name: "Span changes" }).waitFor();
  await page.screenshot({
    path: `${directory}/comparison.png`,
    fullPage: true,
  });
} finally {
  await browser.close();
}
console.log(`Saved debugger screenshots to ${directory}`);
