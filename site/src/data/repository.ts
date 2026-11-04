import bundleJson from "../generated/bundle.json";
import type { Bundle, Completeness } from "./types";

/** The only entry point pages use to read data (DEVELOPMENT_PLAN.md §3). */
export const bundle = bundleJson as unknown as Bundle;

export interface EditionRow {
  exhibitionId: string; exhibitionName: string; editionId: string; year: number;
  assessment: Bundle["exhibitions"][number]["acquisition"];
  lastAcquisition: Bundle["exhibitions"][number]["editions"][number]["lastAcquisition"];
  latest: Bundle["exhibitions"][number]["editions"][number]["datasets"][number] | null;
}

export function getOverview(b: Bundle = bundle) {
  const latest = Object.values(b.datasets);
  const companyIds = new Set(latest.flatMap((d) => d.companies.map((c) => c.companyId)));
  const countries = new Map<string, number>();
  for (const d of latest) for (const c of d.companies) countries.set(c.country ?? "未知", (countries.get(c.country ?? "未知") ?? 0) + 1);

  const rows: EditionRow[] = b.exhibitions.flatMap((ex) => ex.editions.map((ed) => ({
    exhibitionId: ex.exhibitionId, exhibitionName: ex.name, editionId: ed.editionId, year: ed.year,
    assessment: ex.acquisition, lastAcquisition: ed.lastAcquisition,
    latest: ed.datasets.find((d) => d.datasetId === ed.latestDatasetId) ?? null,
  })));
  const acquisition = new Map<string, number>();
  for (const r of rows) { const k = r.lastAcquisition?.status ?? "none"; acquisition.set(k, (acquisition.get(k) ?? 0) + 1); }

  const sortedAnalyses = [...b.analyses].sort((x, y) => y.generatedAt.localeCompare(x.generatedAt));
  return {
    dataOrigin: b.dataOrigin,
    exhibitionCount: b.exhibitions.length,
    companyCount: companyIds.size,
    companyCompleteness: combineCompleteness(latest.map((d) => d.completeness)),
    analyzedCompanyCount: new Set(b.analyses.flatMap((a) => a.analyzedCompanyIds)).size,
    highPriorityCount: b.analyses.reduce((n, a) => n + a.highPriorityRecommendations, 0),
    countryDistribution: [...countries].map(([name, value]) => ({ name, value })).sort((x, y) => y.value - x.value),
    acquisitionDistribution: [...acquisition].map(([status, value]) => ({ status, value })),
    editions: rows,
    latestAnalysis: sortedAnalyses[0] ?? null,
    notices: b.notices,
    source: { ...b.generatedFrom, schemaVersion: b.schemaVersion, indexGeneratedAt: b.indexGeneratedAt },
  };
}

/** Totals are only "complete" when every part is; an unknown official count makes the total unknown (never estimated). */
export function combineCompleteness(parts: Completeness[]): Completeness | null {
  if (parts.length === 0) return null;
  const collected = parts.reduce((n, p) => n + p.collected, 0);
  const official = parts.some((p) => p.official === null) ? null : parts.reduce((n, p) => n + (p.official ?? 0), 0);
  const status = parts.every((p) => p.status === "complete") ? "complete" : parts.some((p) => p.status === "unknown") ? "unknown" : "partial";
  return { status, official, collected };
}
