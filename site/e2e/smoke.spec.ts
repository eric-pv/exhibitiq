import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const SHOTS = process.env.SCREENSHOT_DIR;
const BUILT = new Set(["系統總覽", "參展商與企業情報", "商機分析與評分", "展覽搜尋與新增", "AI 報告中心", "分析設定", "展覽情報與比較", "資料及系統狀態"]); // pages that are no longer 「建置中」
const MENU = ["系統總覽", "展覽搜尋與新增", "展覽情報與比較", "參展商與企業情報", "商機分析與評分", "BXR 產品推薦", "AI 報告中心", "分析設定", "資料及系統狀態"];

test.beforeEach(async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  info.attach("errors", { body: "" });
  (page as unknown as { _errs: string[] })._errs = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as unknown as { _errs: string[] })._errs).toEqual([]);
});

test("desktop: side menu shows 9 items and every page opens", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("/");
  const nav = page.getByTestId("side-nav");
  for (const label of MENU) await expect(nav.getByText(label, { exact: true })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-02-desktop-overview.png`, fullPage: true });
  for (const label of MENU.slice(1)) {
    await nav.getByText(label, { exact: true }).click();
    await expect(page.getByRole("heading", { name: label, level: 2 })).toBeVisible();
    if (BUILT.has(label)) await expect(page.getByTestId("under-construction")).toHaveCount(0);
    else await expect(page.getByTestId("under-construction")).toBeVisible();
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
  await expect(page.getByTestId("kpi-companies")).toContainText("已取得 2 ／ 官方公布 3");
  await page.getByTestId("side-nav").getByText("商機分析與評分", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "商機分析與評分", level: 2 })).toBeVisible();
});

test("overview: synthetic banner, KPI cards from data, charts and data status", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByTestId("data-origin-banner")).toBeVisible();
  await expect(page.getByTestId("kpi-exhibitions")).toContainText("2");
  await expect(page.getByTestId("kpi-companies")).toContainText("已取得 2 ／ 官方公布 3");
  await expect(page.getByTestId("chart-country").locator("svg").first()).toBeVisible();
  await expect(page.getByTestId("chart-acquisition").locator("svg").first()).toBeVisible();
  await expect(page.getByTestId("data-status")).toContainText("沒有可用的資料包");
  await expect(page.getByTestId("latest-analysis")).toContainText("未審核");
  await page.waitForTimeout(500); // let menu and card animations settle before measuring and the screenshot
  // charts stay inside their cards after layout settles
  for (const id of ["chart-country", "chart-acquisition"]) {
    const card = await page.getByTestId(id).boundingBox();
    const svg = await page.getByTestId(id).locator("svg").first().boundingBox();
    expect(svg!.x + svg!.width).toBeLessThanOrEqual(card!.x + card!.width + 1);
  }
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-03-${info.project.name}-overview.png`, fullPage: true });
  await page.getByTestId("kpi-companies").click();
  await expect(page.getByRole("heading", { name: "參展商與企業情報", level: 2 })).toBeVisible();
});

test("company detail (W2-03): list → detail, every field shows its source, source popover", async ({ page }, info) => {
  await page.goto("/#/companies");
  await page.getByTestId("company-link").first().click();
  await expect(page).toHaveURL(/#\/companies\/co_/);
  await expect(page.getByTestId("data-origin-banner")).toBeVisible();
  await expect(page.getByTestId("company-meta")).toContainText("最後更新");
  const fields = page.getByTestId("company-fields");
  await expect(fields.getByTestId("source-ref").first()).toBeVisible();
  await expect(page.getByTestId("company-participations").getByTestId("source-ref").first()).toBeVisible();
  await page.getByTestId("company-sources").getByTestId("source-ref").first().click();
  await expect(page.getByText("內容雜湊")).toBeVisible();
  await page.waitForTimeout(300);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-03-${info.project.name}-company-detail.png`, fullPage: true });
  await page.getByText("返回企業清單").click();
  await expect(page.getByTestId("company-table")).toBeVisible();
});

test("opportunities (W2-04): AI notice, ranking, score breakdown with sources, link to company", async ({ page }, info) => {
  await page.goto("/#/opportunities");
  await expect(page.getByTestId("ai-notice")).toBeVisible();
  await expect(page.getByTestId("score-breakdown").first()).toBeVisible();
  await expect(page.getByTestId("score-breakdown").first().getByText(/資料不足，不計分/).first()).toBeVisible();
  await expect(page.getByTestId("conclusions").locator('[data-claim="ai_inferred"]').first()).toBeVisible();
  await page.waitForTimeout(300);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-04-${info.project.name}-opportunities.png`, fullPage: true });
  await page.getByTestId("ranking-table").getByRole("link").first().click();
  await expect(page).toHaveURL(/#\/companies\/co_/);
});

test("exhibitions (W2-01): list from the dataset index, detail with editions", async ({ page }, info) => {
  await page.goto("/#/exhibitions");
  await expect(page.getByTestId("exhibition-table")).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-01-${info.project.name}-exhibitions.png`, fullPage: true });
  await page.getByTestId("exhibition-link").first().click();
  await expect(page.getByTestId("exhibition-editions")).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-01-${info.project.name}-exhibition-detail.png`, fullPage: true });
});

test("reports (W3-04): report viewer, print layout hides navigation, PDF export", async ({ page }, info) => {
  await page.goto("/#/reports");
  await expect(page.getByTestId("report-viewer")).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w3-04-${info.project.name}-reports.png`, fullPage: true });
  await page.emulateMedia({ media: "print" });
  await expect(page.getByTestId("side-nav")).toBeHidden();
  await expect(page.getByTestId("export-pdf")).toBeHidden();
  await expect(page.getByTestId("report-viewer")).toBeVisible();
  if (info.project.name === "desktop" && SHOTS) await page.pdf({ path: `${SHOTS}/w3-04-report.pdf`, format: "A4", printBackground: true });
});

test("settings (W2-06): add a keyword, it is a local draft and survives reload; export is available", async ({ page }, info) => {
  await page.goto("/#/settings");
  await expect(page.getByTestId("settings-flow")).toBeVisible();
  await page.getByTestId("profile-item").filter({ hasText: "預設詞庫" }).click();
  await page.getByTestId("keyword-add").fill("雷射模擬");
  await page.getByTestId("keyword-add").press("Enter");
  await expect(page.getByTestId("unsubmitted-warning")).toBeVisible();
  await page.reload();
  await page.getByTestId("profile-item").filter({ hasText: "預設詞庫" }).click();
  await expect(page.getByTestId("unsubmitted-warning")).toBeVisible();
  await expect(page.getByTestId("profile-list").getByTestId("state-default-library").locator('[data-state="draft"]')).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-06-${info.project.name}-settings.png`, fullPage: true });
  await page.getByRole("tab", { name: "提交與版本" }).click();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("profile-export").click()]);
  expect(dl.suggestedFilename()).toBe("default-library.json");
});

test("compare (W3-01): editions side by side, missing data shown as 資料不足", async ({ page }, info) => {
  await page.goto("/#/intel");
  await expect(page.getByTestId("compare-table")).toBeVisible();
  await expect(page.getByTestId("compare-table").getByText("資料不足").first()).toBeVisible();
  await page.waitForTimeout(300);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w3-01-${info.project.name}-compare.png`, fullPage: true });
});

test("status (W2-05): acquisition incl. failures, validation, notices", async ({ page }, info) => {
  await page.goto("/#/status");
  await expect(page.getByTestId("status-acquisition")).toBeVisible();
  await expect(page.getByTestId("failed-note")).toBeVisible();
  await page.waitForTimeout(300);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w2-05-${info.project.name}-status.png`, fullPage: true });
});
