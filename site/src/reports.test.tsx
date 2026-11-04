import { render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { ReportViewer } from "./components/ReportViewer";
import { getAnalyses, getAnalysisView } from "./data/repository";
import type { Bundle } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

const G = join(REPO, "data", "samples", "golden", "v1");
const EX = join(REPO, "schemas", "v1", "examples");
const cases = [
  ["example", undefined, join(EX, "analysis", "analysis_result.example.json"), join(EX, "package")],
  ["golden", () => buildBundle({ indexPath: join(G, "dataset_index.json"), analysesDir: join(G, "expected", "analysis") }) as Bundle,
    join(G, "expected", "analysis", "analysis_result.json"), join(G, "package")],
] as const;

test.each(cases)("%s: web ReportViewer has the same sections and conclusions as the Markdown report", (_n, mk, analysis, pkg) => {
  const md = execFileSync("python3", [join(REPO, "skills/exhibitiq/scripts/exhibitiq_tools.py"), "report", analysis, pkg], { encoding: "utf8" });
  const b = mk ? mk() : undefined;
  const a = getAnalyses(b)[0];
  const { container } = render(<ConfigProvider locale={zhTW}><MemoryRouter><ReportViewer view={getAnalysisView(a, b)} b={b} /></MemoryRouter></ConfigProvider>);
  const webHeads = [...container.querySelectorAll("section > h4")].map((h) => h.textContent);
  const mdHeads = md.split("\n").filter((l) => l.startsWith("## ")).map((l) => l.slice(3));
  expect(webHeads).toEqual(mdHeads);
  for (const c of a.detail.conclusions) { expect(md).toContain(c.statement); expect(container.textContent).toContain(c.statement); }
  for (const id of a.evidenceSourceIds) expect(container.textContent).toContain(id);
});

test("reports page: viewer and PDF export button", () => {
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/reports"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getByTestId("report-viewer")).toBeTruthy();
  expect(screen.getByTestId("export-pdf")).toBeTruthy();
});
