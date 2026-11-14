import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("records, inspects, and re-executes a failed run offline", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Record a failure" }).click();
  await expect(
    page.getByRole("heading", { name: "Execution timeline" }),
  ).toBeVisible();
  await expect(
    page.getByText("Inventory response is missing", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("tab", { name: "error" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("ValueError");
  await page.getByRole("button", { name: "Re-execute offline" }).click();
  await expect(page.getByText("All recorded calls matched")).toBeVisible();
  await expect(
    page.getByText("2 / 2 calls matched.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Offline re-execution · recorded responses"),
  ).toBeVisible();
});

test("surfaces a strict replay divergence and missing calls", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Run demo agent" }).click();
  await page.getByRole("button", { name: "Simulate divergence" }).click();
  await expect(page.getByText("Replay divergence detected")).toBeVisible();
  await expect(page.getByText("missing_calls", { exact: true })).toBeVisible();
  await expect(
    page.getByText("ReplayDivergence", { exact: true }).first(),
  ).toBeVisible();
});

test("searches, selects and compares real stored executions", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/demo", {
    data: { request: "Compare example", fail: false },
  });
  await request.post("/api/v1/demo", {
    data: { request: "Compare example", fail: true },
  });
  await page.goto("/?view=executions");
  await page
    .getByRole("textbox", { name: "Search executions" })
    .fill("shopping");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.locator("tbody input[type=checkbox]").nth(0).check();
  await page.locator("tbody input[type=checkbox]").nth(1).check();
  await page.getByRole("button", { name: "Compare (2/2)" }).click();
  await expect(
    page.getByRole("heading", { name: "Find what changed." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Span changes" }),
  ).toBeVisible();
  await expect(page.getByText("added", { exact: true })).toBeVisible();
});

test("keeps the mobile layout within the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your agents, under the hood." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("downloads a complete offline pytest bundle through the debugger proxy", async ({
  page,
  request,
}) => {
  const source = await (
    await request.post("/api/v1/demo", { data: { fail: true } })
  ).json();
  await page.goto(`/?run=${source.id}`);
  await page.getByRole("button", { name: "Export pytest" }).click();
  await expect(page.getByLabel("Python entrypoint")).toHaveValue(
    "agentreplay_examples.agent:shopping_agent",
  );
  await expect(
    page.getByText("It passes when that failure is reproduced.", {
      exact: false,
    }),
  ).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download test bundle" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(
    `agentreplay-regression-${source.id.replaceAll("-", "").slice(0, 12)}.zip`,
  );
  const data = await readFile((await download.path())!);
  expect(data.subarray(0, 4).toString("hex")).toBe("504b0304");
  expect(data.includes(Buffer.from("README.md"))).toBeTruthy();
  const response = await request.get(
    `/api/v1/runs/${source.id}/regression?entrypoint=agentreplay_examples.agent%3Ashopping_agent`,
  );
  expect(response.headers()["content-type"]).toBe("application/zip");
  expect(data.equals(await response.body())).toBeTruthy();
  await expect(page.getByRole("status")).toContainText(
    "Test bundle downloaded",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("shows an actionable error for an invalid regression entrypoint", async ({
  page,
  request,
}) => {
  const source = await (
    await request.post("/api/v1/demo", { data: {} })
  ).json();
  await page.goto(`/?run=${source.id}`);
  await page.getByRole("button", { name: "Export pytest" }).click();
  await page.getByLabel("Python entrypoint").fill("invalid-entrypoint");
  await page.getByRole("button", { name: "Download test bundle" }).click();
  await expect(
    page.getByRole("region", { name: "Regression test" }).getByRole("alert"),
  ).toContainText("Use a Python entrypoint");
});
