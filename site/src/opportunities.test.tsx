import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { claimKindOf, getOpportunityView } from "./data/repository";
import type { Bundle } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

const G = join(REPO, "data", "samples", "golden", "v1");
const golden = () => buildBundle({ indexPath: join(G, "dataset_index.json"), analysesDir: join(G, "expected", "analysis") }) as Bundle;

test.each([["example", undefined], ["golden", golden]])("%s: ranking ordered by rank; totals equal the sum of scored factors; unscored factors have 0 points and no evidence", (_n, mk) => {
  const v = getOpportunityView(null, mk ? mk() : undefined)!;
  expect(v.ranking.length).toBeGreaterThan(0);
  const ranks = v.ranking.map((r) => r.rank ?? Infinity);
  expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
  for (const r of v.ranking) {
    expect(r.total).toBe(r.score.factors.filter((f) => f.status === "scored").reduce((n, f) => n + f.points, 0));
    for (const f of r.score.factors.filter((f) => f.status === "insufficient_data")) expect(f.points).toBe(0);
    for (const f of r.score.factors.filter((f) => f.status === "scored")) expect(f.sourceIds.length + f.claimIds.length).toBeGreaterThan(0);
    for (const id of r.score.factors.flatMap((f) => f.sourceIds)) expect("missing" in v.source(id)).toBe(false);
  }
});

test("labels: facts keep their verification status, inference is AI, unknown is insufficient data", () => {
  expect(claimKindOf({ claimType: "fact", verificationStatus: "verified" })).toBe("verified");
  expect(claimKindOf({ claimType: "inference", verificationStatus: null })).toBe("ai_inferred");
  expect(claimKindOf({ claimType: "unknown", verificationStatus: null })).toBe("insufficient_data");
});

test("bundle build stops when an analysis cites a source that is not in its input package", () => {
  const tmp = mkdtempSync(join(tmpdir(), "exq-w204-"));
  try {
    const ex = join(REPO, "schemas", "v1", "examples");
    cpSync(join(ex, "analysis"), join(tmp, "analysis"), { recursive: true });
    const f = join(tmp, "analysis", "analysis_result.example.json");
    const a = JSON.parse(readFileSync(f, "utf8"));
    a.scores[0].factors[0].evidence_source_ids = ["src_01JCS0000000000000000000ZZ"];
    writeFileSync(f, JSON.stringify(a));
    expect(() => buildBundle({ indexPath: join(ex, "index", "dataset_index.example.json"), analysesDir: join(tmp, "analysis") })).toThrow(/not in .*sources\.jsonl/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("opportunities page: AI notice, ranking with breakdown, insufficient factors marked, recommendations and conclusions labelled", () => {
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/opportunities"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getByTestId("ai-notice")).toBeTruthy();
  expect(screen.getByTestId("data-origin-banner")).toBeTruthy();
  const breakdown = screen.getAllByTestId("score-breakdown")[0];
  expect(breakdown.querySelectorAll('[data-factor-status="insufficient_data"]').length).toBeGreaterThan(0);
  expect(within(breakdown).getAllByTestId("source-ref").length).toBeGreaterThan(0);
  expect(within(screen.getByTestId("recommendations")).getAllByText("AI 推論").length).toBeGreaterThan(0);
  const concl = screen.getByTestId("conclusions");
  expect(concl.querySelector('[data-claim="ai_inferred"]')).toBeTruthy();
  expect(concl.querySelector('[data-claim="insufficient_data"]')).toBeTruthy();
  expect(screen.getByTestId("csv-export")).toBeTruthy();
});
