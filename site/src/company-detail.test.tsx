import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { bundle, getCompanyAnalyses, getCompanyDetail, getCompanyRows } from "./data/repository";
import type { Bundle } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

const withFieldSource = getCompanyRows().find((r) => Object.keys(bundle.datasets[r.key.split(":")[0]].companies.find((c) => c.companyId === r.companyId)!.detail.fieldSources).length > 0)!;

test("detail: field-level sources win; other fields fall back to record-level sources (schema rule)", () => {
  const d = getCompanyDetail(withFieldSource.companyId)!;
  const raw = bundle.datasets[withFieldSource.key.split(":")[0]].companies.find((c) => c.companyId === d.companyId)!.detail;
  const [field, ids] = Object.entries(raw.fieldSources)[0];
  const f = d.fields.find((x) => x.key === field)!;
  expect(f.recordLevel).toBe(false);
  expect(f.sources.map((s) => s.sourceId)).toEqual(ids);
  const name = d.fields.find((x) => x.key === "name")!;
  expect(name.recordLevel).toBe(true);
  expect(name.sources.map((s) => s.sourceId)).toEqual(raw.sourceIds);
  // a field without a value shows no source (nothing is invented)
  for (const x of d.fields.filter((x) => x.value === null)) expect(x.sources).toEqual([]);
  expect(d.participations.length).toBeGreaterThan(0);
  for (const p of d.participations) expect(p.sources.length).toBeGreaterThan(0);
});

test("detail: last updated is the latest real timestamp, never later than the data", () => {
  const d = getCompanyDetail(withFieldSource.companyId)!;
  const stamps = [d.packageCreatedAt, ...d.participations.map((p) => p.lastSeenAt), ...d.fields.flatMap((f) => f.sources).map((s) => ("missing" in s ? null : s.retrievedAt))]
    .filter((s): s is string => !!s);
  expect(d.lastUpdated).toBe(stamps.sort().at(-1));
});

test("detail: unknown company id returns null", () => {
  expect(getCompanyDetail("co_DOES_NOT_EXIST")).toBeNull();
});

test("detail: every golden-sample company resolves all of its sources", () => {
  const g = join(REPO, "data", "samples", "golden", "v1");
  const b = buildBundle({ indexPath: join(g, "dataset_index.json"), analysesDir: join(g, "expected", "analysis") }) as Bundle;
  const ids = new Set(Object.values(b.datasets).flatMap((ds) => ds.companies.map((c) => c.companyId)));
  expect(ids.size).toBeGreaterThan(0);
  for (const id of ids) {
    const d = getCompanyDetail(id, b)!;
    const all = [...d.fields.flatMap((f) => f.sources), ...d.aliases.flatMap((a) => a.sources), ...d.participations.flatMap((p) => p.sources)];
    expect(all.filter((s) => "missing" in s), id).toEqual([]);
  }
});

test("bundle build stops when a record cites a source that is not in sources.jsonl", () => {
  const tmp = mkdtempSync(join(tmpdir(), "exq-w203-"));
  try {
    const src = join(REPO, "schemas", "v1", "examples");
    cpSync(join(src, "package"), join(tmp, "package"), { recursive: true });
    const sources = readFileSync(join(tmp, "package", "sources.jsonl"), "utf8").split("\n").filter(Boolean);
    writeFileSync(join(tmp, "package", "sources.jsonl"), sources.slice(0, 1).join("\n") + "\n"); // drop the 2nd source
    const index = JSON.parse(readFileSync(join(src, "index", "dataset_index.example.json"), "utf8"));
    for (const ex of index.exhibitions) for (const ed of ex.editions) for (const ds of ed.datasets) ds.location.locator = relative(REPO, join(tmp, "package"));
    writeFileSync(join(tmp, "index.json"), JSON.stringify(index));
    expect(() => buildBundle({ indexPath: join(tmp, "index.json"), analysesDir: join(tmp, "none") })).toThrow(/not in sources\.jsonl/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

const renderAt = (path: string) => render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></ConfigProvider>);

test("detail page: fields with sources, unknowns shown as 未知, participations and source list", () => {
  renderAt(`/companies/${withFieldSource.companyId}`);
  expect(screen.getByRole("heading", { level: 2, name: withFieldSource.name })).toBeTruthy();
  const fields = screen.getByTestId("company-fields");
  expect(within(fields).getAllByTestId("source-ref").length).toBeGreaterThan(0);
  expect(within(fields).getAllByText("未知").length).toBeGreaterThan(0); // e.g. no Chinese name in the sample
  expect(within(screen.getByTestId("company-participations")).getAllByTestId("source-ref").length).toBeGreaterThan(0);
  expect(within(screen.getByTestId("company-sources")).getAllByTestId("source-ref").length).toBeGreaterThan(0);
  expect(screen.getByTestId("company-meta").textContent).toContain("最後更新");
  expect(screen.getByTestId("data-origin-banner")).toBeTruthy();
});

test("detail page: unknown company shows an empty state with a way back", () => {
  renderAt("/companies/co_DOES_NOT_EXIST");
  expect(screen.getByText(/找不到企業 co_DOES_NOT_EXIST/)).toBeTruthy();
  expect(screen.getByText("返回企業清單")).toBeTruthy();
});

test("company list links each name to its detail page", () => {
  renderAt("/companies");
  const links = screen.getAllByTestId("company-link");
  expect(links[0].getAttribute("href")).toMatch(/^\/companies\/co_/);
});

test("W3-06: company ↔ analyses ↔ exhibition links (scores, relationships, mentions); nothing for an unmentioned company", () => {
  const scored = bundle.analyses.flatMap((a) => a.detail.scores.map((s) => s.subject)).find((s) => s.entity_type === "company")!.entity_id;
  const xs = getCompanyAnalyses(scored);
  expect(xs.length).toBeGreaterThan(0);
  expect(xs.some((x) => x.score && x.score.max > 0)).toBe(true);
  expect(getCompanyAnalyses("co_does_not_exist")).toEqual([]);
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[`/companies/${scored}`]}><App /></MemoryRouter></ConfigProvider>);
  const card = screen.getByTestId("company-analyses");
  expect(within(card).getAllByTestId("company-analysis-report")[0].getAttribute("href")).toMatch(/^\/reports\?analysis=/);
  expect(within(card).getAllByTestId("company-analysis-opportunity")[0].getAttribute("href")).toMatch(/^\/opportunities\?analysis=/);
  expect(screen.getAllByTestId("participation-exhibition")[0].getAttribute("href")).toMatch(/^\/exhibitions\//);
});
