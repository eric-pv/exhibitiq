import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const SHOTS = process.env.SCREENSHOT_DIR;
const MENU = ["系統總覽", "展覽搜尋與新增", "展覽情報與比較", "參展商與企業情報", "商機分析與評分", "BXR 產品推薦", "AI 報告中心", "資料及系統狀態"];

test.beforeEach(async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  info.attach("errors", { body: "" });
  (page as unknown as { _errs: string[] })._errs = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as unknown as { _errs: string[] })._errs).toEqual([]);
});

test("desktop: side menu shows 8 items and every page opens", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("/");
  const nav = page.getByTestId("side-nav");
  for (const label of MENU) await expect(nav.getByText(label, { exact: true })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-02-desktop-overview.png`, fullPage: true });
  for (const label of MENU) {
    await nav.getByText(label, { exact: true }).click();
    await expect(page.getByRole("heading", { name: label, level: 2 })).toBeVisible();
    await expect(page.getByTestId("under-construction")).toBeVisible();
  }
  await page.goto("/#/design");
  await expect(page.getByText("AI 推論")).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-02-desktop-design.png`, fullPage: true });
});

test("mobile: menu is collapsed and opens from the trigger", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile");
  await page.goto("/");
  const nav = page.getByTestId("side-nav");
  await expect(nav.getByText("AI 報告中心", { exact: true })).toBeHidden();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-02-mobile-closed.png` });
  await page.locator(".ant-layout-sider-zero-width-trigger").click();
  await expect(nav.getByText("AI 報告中心", { exact: true })).toBeVisible();
  // The overlay must not squeeze the page: content keeps the full viewport width.
  const contentBox = await page.locator(".ant-layout-content").boundingBox();
  expect(contentBox?.width ?? 0).toBeGreaterThan(350);
  await page.waitForTimeout(400); // let the open animation finish before the screenshot
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-02-mobile-open.png` });
  await nav.getByText("AI 報告中心", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "AI 報告中心", level: 2 })).toBeVisible();
  await expect(nav.getByText("系統總覽", { exact: true })).toBeHidden();
});

test("single-file build opens from disk and navigates", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  const file = resolve("dist-single/index.html");
  test.skip(!existsSync(file), "run `npm run build:single` first");
  await page.goto(pathToFileURL(file).href);
  await page.getByTestId("side-nav").getByText("商機分析與評分", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "商機分析與評分", level: 2 })).toBeVisible();
});
