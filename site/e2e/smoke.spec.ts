import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const SHOTS = process.env.SCREENSHOT_DIR;

test("built site renders with zh-TW locale and an ECharts SVG", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "ExhibitIQ Dashboard" })).toBeVisible();
  await expect(page.getByText("前端骨架（W1-01）")).toBeVisible();
  await expect(page.getByTestId("chart-card").locator("svg").first()).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-Hant");
  expect(errors).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/w1-01-${info.project.name}.png`, fullPage: true });
});

test("single-file build opens from disk without a server", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "one run is enough");
  const file = resolve("dist-single/index.html");
  test.skip(!existsSync(file), "run `npm run build:single` first");
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(pathToFileURL(file).href);
  await expect(page.getByRole("heading", { name: "ExhibitIQ Dashboard" })).toBeVisible();
  await expect(page.getByTestId("chart-card").locator("svg").first()).toBeVisible();
  expect(errors).toEqual([]);
});
