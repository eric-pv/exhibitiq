import { expect, test } from "@playwright/test";

/**
 * W4-01: the main operating flow as ONE test, in the order of the competition demo script
 * (docs/acceptance/demo-script.md, A3-06): 總覽 → 展覽 → 比較與歷史趨勢 → 企業 → 商機 → 產品建議 → 報告 → PDF。
 * Navigation only through the side menu and in-page links (no direct URLs after the first page).
 */
test("main flow: overview → exhibition → compare/history → company → opportunity → products → report → PDF", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const nav = page.getByTestId("side-nav");
  const go = async (label: string) => {
    await nav.getByText(label, { exact: true }).click();
    await expect(page.getByRole("heading", { name: label, level: 2 })).toBeVisible();
  };

  // 1. 系統總覽：資料類型橫幅、統計卡片
  await page.goto("/");
  await expect(page.getByTestId("data-origin-banner")).toBeVisible();
  await expect(page.getByTestId("kpi-companies")).toBeVisible();

  // 2. 展覽搜尋與新增 → 展覽詳情（取得方式、各屆次）
  await go("展覽搜尋與新增");
  await page.getByTestId("exhibition-link").first().click();
  await expect(page.getByTestId("exhibition-editions")).toBeVisible();

  // 3. 展覽情報與比較：並排比較、歷史趨勢（單一年度 → 資料不足）
  await go("展覽情報與比較");
  await expect(page.getByTestId("compare-table")).toBeVisible();
  await expect(page.getByTestId("history")).toContainText("資料不足");

  // 4. 參展商與企業情報 → 企業詳情（欄位來源）
  await go("參展商與企業情報");
  await page.getByTestId("company-link").first().click();
  await expect(page.getByTestId("company-fields").getByTestId("source-ref").first()).toBeVisible();

  // 5. 商機分析與評分：AI 推論標示、評分拆解、排名連到企業
  await go("商機分析與評分");
  await expect(page.getByTestId("ai-notice")).toBeVisible();
  await expect(page.getByTestId("score-breakdown").first()).toBeVisible();
  await expect(page.getByTestId("ranking-table").getByRole("link").first()).toBeVisible();

  // 6. BXR 產品推薦：只顯示已核定產品卡
  await go("BXR 產品推薦");
  await expect(page.getByTestId("product-card").first()).toBeVisible();

  // 7. AI 報告中心 → 列印（PDF）版面
  await go("AI 報告中心");
  await expect(page.getByTestId("report-viewer")).toBeVisible();
  await expect(page.getByTestId("export-pdf")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByTestId("side-nav")).toBeHidden();
  await expect(page.getByTestId("report-viewer")).toBeVisible();
  const pdf = await page.pdf({ format: "A4", printBackground: true });
  expect(pdf.byteLength).toBeGreaterThan(10_000);

  expect(errors).toEqual([]);
});

test("W3-06 cross-page links: chart → filtered list, company → report, report ↔ opportunities, exhibition → history", async ({ page }, info) => {
  test.skip(info.project.name === "mobile"); // same links; the menu flow on mobile is covered in smoke.spec.ts
  await page.goto("/#/opportunities");
  await page.getByTestId("ranking-table").getByRole("link").first().click();
  await expect(page.getByTestId("company-analyses")).toBeVisible();
  await page.getByTestId("company-analysis-report").first().click();
  await expect(page.getByTestId("report-viewer")).toBeVisible();
  await page.getByTestId("report-opportunity-link").click();
  await expect(page.getByTestId("ranking-table")).toBeVisible();
  await page.getByTestId("opportunity-exhibition-link").click();
  await expect(page.getByTestId("exhibition-editions")).toBeVisible();
  await page.getByTestId("exhibition-intel-link").click();
  await expect(page).toHaveURL(/#\/intel\?h=/);
  await expect(page.getByTestId("history")).toBeVisible();
  await page.getByTestId("compare-exhibition-link").first().click();
  await expect(page.getByTestId("exhibition-editions")).toBeVisible();
});

test("W3-07 add exhibition: form → valid registration → download; nothing is sent", async ({ page }, info) => {
  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() !== "GET") posts.push(r.url()); });
  await page.goto("/#/exhibitions");
  await page.getByTestId("add-toggle").click();
  await page.getByTestId("add-name").fill("New Fair");
  await page.getByTestId("add-country").fill("TW");
  await page.getByTestId("add-website").fill("https://new-fair.example/");
  await page.getByTestId("add-requested-by").fill("Eric");
  await page.getByTestId("add-years").click();
  await page.locator(".ant-select-item-option").first().click();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("add-valid")).toBeVisible();
  await expect(page.getByTestId("add-json")).toContainText('"request_channel": "dashboard_form"');
  await expect(page.getByTestId("add-no-workflow")).toBeVisible();
  if (info.project.name === "desktop") {
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("add-download").click()]);
    expect(dl.suggestedFilename()).toBe("registration.json");
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(posts).toEqual([]);
});
