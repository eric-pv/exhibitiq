import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, keywordHit, REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { getComparison, getOverview } from "./data/repository";
import type { Bundle } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

/** Example index + golden index merged: two structurally different exhibitions, plus one edition without a package. */
function twoExhibitions(): Bundle {
  const ex = JSON.parse(readFileSync(join(REPO, "schemas/v1/examples/index/dataset_index.example.json"), "utf8"));
  const g = JSON.parse(readFileSync(join(REPO, "data/samples/golden/v1/dataset_index.json"), "utf8"));
  ex.exhibitions.push(...g.exhibitions);
  const dir = mkdtempSync(join(tmpdir(), "cmp-"));
  writeFileSync(join(dir, "index.json"), JSON.stringify(ex));
  return buildBundle({ indexPath: join(dir, "index.json"), analysesDir: join(REPO, "schemas/v1/examples/analysis") }) as Bundle;
}

test("keyword rule matches the Python rule", () => {
  expect(keywordHit("Simulation", "SIMULATIONS & Training")).toBe(true);
  expect(keywordHit("Sim", "Simulation")).toBe(false);
  expect(keywordHit("模擬", "射擊模擬訓練")).toBe(true);
});

test("comparison: same metrics for every selected edition; no package -> 資料不足 (null); counts equal Python compare", () => {
  const b = twoExhibitions();
  const eds = getOverview(b).editions;
  const v = getComparison(eds.map((e) => e.editionId), "default-library", b);
  expect(v.columns.length).toBe(eds.length);
  const empty = v.columns.find((c) => !c.dataset)!;
  expect(empty.companyCount).toBeNull();
  const withData = v.columns.filter((c) => c.dataset);
  expect(withData.length).toBe(2);
  const py = JSON.parse(execFileSync("python3", [join(REPO, "skills/exhibitiq/scripts/exhibitiq_tools.py"), "compare",
    ...withData.map((c) => join(REPO, eds.find((e) => e.editionId === c.editionId)!.latest!.datasetId.startsWith("golden") ? "data/samples/golden/v1/package" : "schemas/v1/examples/package"))], { encoding: "utf8" }));
  for (const col of withData) {
    const p = py.packages.find((x: { dataset_id: string }) => x.dataset_id === col.dataset!.datasetId);
    for (const [term, k] of Object.entries(col.keywords)) expect(k.count, term).toBe(p.keywords[term].count);
    for (const k of Object.values(col.keywords)) if (col.dataset!.completeness.status !== "complete") expect(k.share).toBeNull();
  }
});

test("compare page renders the side-by-side table from the URL selection", () => {
  const eds = getOverview().editions;
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[`/intel?e=${eds.map((e) => e.editionId).join(",")}`]}><App /></MemoryRouter></ConfigProvider>);
  const table = screen.getByTestId("compare-table");
  for (const e of eds) expect(within(table).getAllByText(`${e.exhibitionName}（${e.year}）`).length).toBeGreaterThan(0);
  expect(within(table).getAllByText("資料不足").length).toBeGreaterThan(0);
});
