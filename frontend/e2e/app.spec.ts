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
  await expect(page.getByText("UX Score", { exact: true })).toBeVisible();
  await expect(page.getByText("Action Timeline")).toBeVisible();

  // Friction points render evidence + a "Why did this happen?" panel when
  // the session produced any, and the timeline shows persisted screenshots.
  const whyButtons = page.getByRole("button", { name: "Why did this happen?" });
  if (await whyButtons.count() > 0) {
    await whyButtons.first().click();
    await expect(page.getByText("Observed behavior:")).toBeVisible();
  }
});
