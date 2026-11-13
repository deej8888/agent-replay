import { expect, test } from "@playwright/test";

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
