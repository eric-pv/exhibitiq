import { expect, test } from "@playwright/test";

/** W4-02: every main page on desktop, tablet and phone: renders without errors and without horizontal page scroll. */
const PAGES = ["/", "/exhibitions", "/intel", "/companies", "/opportunities", "/products", "/reports", "/settings", "/status"];
const SHOTS = process.env.SCREENSHOT_DIR;

for (const path of PAGES) {
  test(`layout ${path}`, async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`/#${path}`);
    await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
    await page.waitForTimeout(400);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, "horizontal page scroll").toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/w4-02-${info.project.name}${path === "/" ? "-overview" : path.replace(/\//g, "-")}.png`, fullPage: true });
  });
}

/** W3-06: detail pages too (reached through their first list link, so no exhibition or company is hard-coded). */
for (const [list, link, ready] of [["/exhibitions", "exhibition-link", "exhibition-editions"], ["/companies", "company-link", "company-analyses"]] as const) {
  test(`layout detail from ${list}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`/#${list}`);
    await page.getByTestId(link).first().click();
    await expect(page.getByTestId(ready)).toBeVisible();
    await page.waitForTimeout(400);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, "horizontal page scroll").toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  });
}
