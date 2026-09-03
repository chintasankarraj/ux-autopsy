import { test, expect } from "@playwright/test";

test("dashboard loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("WHY");
});

test("create and complete a demo test end-to-end", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/new?demo=1");
  await page.getByRole("button", { name: "Start UX Test" }).click();
  await page.waitForURL(/\/sessions\//, { timeout: 150_000 });
  await expect(page.getByText("UX Score")).toBeVisible();
  await expect(page.getByText("Action Timeline")).toBeVisible();
});
