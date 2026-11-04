import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { combineCompleteness, getOverview } from "./data/repository";
import type { Bundle } from "./data/types";
import { antdTheme } from "./theme/tokens";

// jsdom has no layout engine: stub ECharts (real rendering is covered by Playwright).
vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

const EXAMPLES = join(REPO, "schemas", "v1", "examples");

describe("bundle builder", () => {
  test("builds from the example index; every number comes from the files", () => {
    const b = buildBundle({ indexPath: join(EXAMPLES, "index", "dataset_index.example.json"), analysesDir: join(EXAMPLES, "analysis") }) as Bundle;
    const o = getOverview(b);
    const manifest = JSON.parse(readFileSync(join(EXAMPLES, "package", "manifest.json"), "utf8"));
    expect(o.exhibitionCount).toBe(2);
    expect(o.companyCount).toBe(manifest.record_counts.companies);
    expect(o.companyCompleteness).toEqual({
      status: manifest.completeness_status,
      official: manifest.completeness.official_exhibitor_count,
      collected: manifest.completeness.collected_participation_count,
    });
    expect(o.analyzedCompanyCount).toBe(2);
    expect(o.highPriorityCount).toBe(1);
    expect(o.dataOrigin).toBe("synthetic");
    // the failed acquisition is shown, not hidden
    expect(o.acquisitionDistribution).toEqual(expect.arrayContaining([{ status: "failed", value: 1 }, { status: "succeeded", value: 1 }]));
  });

  test("rejects an index that does not match the schema", () => {
    const dir = mkdtempSync(join(tmpdir(), "bundle-"));
    const bad = JSON.parse(readFileSync(join(EXAMPLES, "index", "dataset_index.example.json"), "utf8"));
    delete bad.exhibitions[0].acquisition;
    writeFileSync(join(dir, "index.json"), JSON.stringify(bad));
    expect(() => buildBundle({ indexPath: join(dir, "index.json"), analysesDir: dir })).toThrow(/dataset_index\.schema\.json/);
  });

  test("rejects a package whose hash differs from the index", () => {
    const dir = mkdtempSync(join(tmpdir(), "bundle-"));
    const idx = JSON.parse(readFileSync(join(EXAMPLES, "index", "dataset_index.example.json"), "utf8"));
    idx.exhibitions[0].editions[0].datasets[0].content_hash = "sha256:" + "0".repeat(64);
    writeFileSync(join(dir, "index.json"), JSON.stringify(idx));
    expect(() => buildBundle({ indexPath: join(dir, "index.json"), analysesDir: dir })).toThrow(/content_hash/);
  });

  test("generic: a renamed exhibition flows through without code changes", () => {
    const dir = mkdtempSync(join(tmpdir(), "bundle-"));
    cpSync(join(EXAMPLES, "index", "dataset_index.example.json"), join(dir, "index.json"));
    const idx = JSON.parse(readFileSync(join(dir, "index.json"), "utf8"));
    idx.exhibitions[1].name = "Another Synthetic Show";
    idx.exhibitions[1].name_zh_hant = "另一個合成展覽";
    writeFileSync(join(dir, "index.json"), JSON.stringify(idx));
    const noAnalyses = mkdtempSync(join(tmpdir(), "analyses-"));
    const o = getOverview(buildBundle({ indexPath: join(dir, "index.json"), analysesDir: noAnalyses }) as Bundle);
    expect(o.editions.map((e) => e.exhibitionName)).toContain("另一個合成展覽");
    expect(o.latestAnalysis).toBeNull(); // no analyses given → shown as empty, not invented
  });
});

describe("completeness totals are never estimated", () => {
  test("an unknown official count makes the total unknown", () => {
    expect(combineCompleteness([
      { status: "complete", official: 3, collected: 3 },
      { status: "partial", official: null, collected: 1 },
    ])).toEqual({ status: "partial", official: null, collected: 4 });
    expect(combineCompleteness([])).toBeNull();
  });
});

describe("overview page", () => {
  test("shows synthetic banner, 4 KPI cards, both charts, data status and latest analysis", () => {
    render(<ConfigProvider locale={zhTW} theme={antdTheme}><MemoryRouter initialEntries={["/"]}><App /></MemoryRouter></ConfigProvider>);
    expect(screen.getByTestId("data-origin-banner")).toBeTruthy();
    for (const id of ["kpi-exhibitions", "kpi-companies", "kpi-analyzed", "kpi-priority"]) expect(screen.getByTestId(id)).toBeTruthy();
    expect(within(screen.getByTestId("kpi-companies")).getByText("不完整")).toBeTruthy();
    expect(within(screen.getByTestId("kpi-companies")).getByText(/已取得 2 ／ 官方公布 3/)).toBeTruthy();
    expect(screen.getByTestId("chart-country")).toBeTruthy();
    expect(screen.getByTestId("chart-acquisition")).toBeTruthy();
    const status = screen.getByTestId("data-status");
    expect(within(status).getByText("無法取得")).toBeTruthy();
    expect(within(status).getByText("沒有可用的資料包")).toBeTruthy();
    expect(within(screen.getByTestId("latest-analysis")).getByText("未審核")).toBeTruthy();
    expect(screen.getByTestId("data-source").textContent).toContain("Schema 1.0.0-draft.3");
  });
});
