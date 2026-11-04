import bundleJson from "../generated/bundle.json";
import type { AnalysisDetail, Bundle, Completeness, FieldSources, SourceInfo } from "./types";

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

export interface CompanyRow {
  key: string; companyId: string; name: string; aliases: string[]; country: string | null; verificationStatus: string;
  exhibitionId: string; exhibitionName: string; year: number; listed: boolean; booths: string[]; dataOrigin: "synthetic" | "collected";
}

/** One row per company per latest dataset (a company at two exhibitions appears twice). */
export function getCompanyRows(b: Bundle = bundle): CompanyRow[] {
  const names = new Map(b.exhibitions.map((e) => [e.exhibitionId, e.name]));
  const years = new Map(b.exhibitions.flatMap((e) => e.editions.map((ed) => [ed.editionId, ed.year] as const)));
  return Object.values(b.datasets).flatMap((d) => d.companies.map((c) => ({
    key: `${d.datasetId}:${c.companyId}`, ...c, exhibitionId: d.exhibitionId, exhibitionName: names.get(d.exhibitionId) ?? d.exhibitionId,
    year: years.get(d.editionId) ?? 0, dataOrigin: d.dataOrigin,
  })));
}

export function matchesQuery(r: CompanyRow, q: string): boolean {
  const s = q.trim().toLowerCase();
  return !s || [r.name, ...r.aliases].some((n) => n.toLowerCase().includes(s));
}

/** CSV with UTF-8 BOM so Excel opens Chinese text correctly. */
export function toCsv(headers: readonly string[], rows: (string | number | null)[][]): string {
  const esc = (v: string | number | null) => { const s = v === null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return "\uFEFF" + [headers, ...rows].map((r) => r.map(esc).join(",")).join("\r\n") + "\r\n";
}

/** A cited source, resolved inside the package that cites it. `missing` never happens for bundles that passed build-bundle. */
export type ResolvedSource = SourceInfo | { sourceId: string; missing: true };

export interface DetailField {
  key: string; value: string | string[] | null; sources: ResolvedSource[];
  /** true when the field has no field-level source and the record-level sources apply (schema rule). */
  recordLevel: boolean;
}

export interface CompanyDetail {
  companyId: string; name: string; verificationStatus: string; dataOrigin: "synthetic" | "collected";
  status: "active" | "merged"; mergedInto: string | null; notes: string | null;
  fields: DetailField[];
  aliases: { name: string; lang: string | null; sources: ResolvedSource[] }[];
  participations: {
    key: string; exhibitionId: string; exhibitionName: string; year: number; editionId: string; datasetId: string;
    nameAsListed: string; participationType: string; listingStatus: "listed" | "removed"; booth: string | null; hall: string | null;
    countryAsListed: string | null; categories: string[]; products: string[]; firstSeenAt: string | null; lastSeenAt: string | null;
    verificationStatus: string; sources: ResolvedSource[]; notes: string | null;
  }[];
  /** Latest of: participation last_seen_at, cited source retrieved_at, package created_at. Never estimated. */
  lastUpdated: string;
  packageCreatedAt: string; datasetId: string;
}

/** Fields shown on the detail page, in display order (company.schema.json names). */
export const COMPANY_FIELDS = ["name", "name_en", "name_zh_hant", "country", "website", "domains", "description", "first_seen_at"] as const;

/**
 * All facts about one company across the latest packages (W2-03). The newest package's company record is primary;
 * participations from every package are listed. Returns null when the company is not in any latest package.
 */
export function getCompanyDetail(companyId: string, b: Bundle = bundle): CompanyDetail | null {
  const names = new Map(b.exhibitions.map((e) => [e.exhibitionId, e.name]));
  const years = new Map(b.exhibitions.flatMap((e) => e.editions.map((ed) => [ed.editionId, ed.year] as const)));
  const hits = Object.values(b.datasets)
    .flatMap((d) => d.companies.filter((c) => c.companyId === companyId).map((c) => ({ d, c })))
    .sort((x, y) => y.d.createdAt.localeCompare(x.d.createdAt));
  if (hits.length === 0) return null;
  const { d: primaryDs, c: primary } = hits[0];
  const resolve = (ds: (typeof hits)[number]["d"], ids: string[]): ResolvedSource[] =>
    ids.map((id) => ds.sources[id] ?? { sourceId: id, missing: true as const });
  const fieldOf = (fs: FieldSources, recordIds: string[], key: string) =>
    fs[key] ? { ids: fs[key], recordLevel: false } : { ids: recordIds, recordLevel: true };
  const r = primary.detail;
  const values: Record<(typeof COMPANY_FIELDS)[number], string | string[] | null> = {
    name: primary.name, name_en: r.nameEn, name_zh_hant: r.nameZhHant, country: primary.country, website: r.website,
    domains: r.domains.length ? r.domains : null, description: r.description, first_seen_at: r.firstSeenAt,
  };
  const fields = COMPANY_FIELDS.map((key) => {
    const value = values[key];
    if (value === null) return { key, value, sources: [], recordLevel: false }; // no value → no source to show
    const f = fieldOf(r.fieldSources, r.sourceIds, key);
    return { key, value, sources: resolve(primaryDs, f.ids), recordLevel: f.recordLevel };
  });

  const aliases = new Map<string, CompanyDetail["aliases"][number]>();
  for (const { d, c } of hits) for (const a of c.detail.aliases) if (!aliases.has(a.name)) aliases.set(a.name, { name: a.name, lang: a.lang, sources: resolve(d, a.sourceIds) });

  const participations = hits.flatMap(({ d, c }) => c.detail.participations.map((p) => ({
    key: `${d.datasetId}:${p.participationId}`, exhibitionId: d.exhibitionId, exhibitionName: names.get(d.exhibitionId) ?? d.exhibitionId,
    year: years.get(p.editionId) ?? years.get(d.editionId) ?? 0, editionId: p.editionId, datasetId: d.datasetId,
    nameAsListed: p.nameAsListed, participationType: p.participationType, listingStatus: p.listingStatus, booth: p.booth, hall: p.hall,
    countryAsListed: p.countryAsListed, categories: p.categories, products: p.products, firstSeenAt: p.firstSeenAt, lastSeenAt: p.lastSeenAt,
    verificationStatus: p.verificationStatus, sources: resolve(d, p.sourceIds), notes: p.notes,
  }))).sort((x, y) => y.year - x.year || x.exhibitionName.localeCompare(y.exhibitionName));

  const stamps = [
    primaryDs.createdAt,
    ...participations.map((p) => p.lastSeenAt).filter((s): s is string => !!s),
    ...[...fields.flatMap((f) => f.sources), ...participations.flatMap((p) => p.sources)].flatMap((s) => ("missing" in s ? [] : [s.retrievedAt])),
  ];
  return {
    companyId, name: primary.name, verificationStatus: primary.verificationStatus, dataOrigin: primaryDs.dataOrigin,
    status: r.status, mergedInto: r.mergedInto, notes: r.notes, fields, aliases: [...aliases.values()], participations,
    lastUpdated: stamps.reduce((a, s) => (s > a ? s : a)), packageCreatedAt: primaryDs.createdAt, datasetId: primaryDs.datasetId,
  };
}

type Analysis = Bundle["analyses"][number];
type Conclusion = AnalysisDetail["conclusions"][number];

/** How a conclusion is labelled: sourced facts keep their verification status; everything else is AI inference or unknown. */
export function claimKindOf(c: Pick<Conclusion, "claimType" | "verificationStatus">): string {
  return c.claimType === "fact" ? c.verificationStatus ?? "unverified" : c.claimType === "inference" ? "ai_inferred" : "insufficient_data";
}

export interface RankingRow {
  key: string; rank: number | null; companyId: string; companyName: string; total: number; max: number;
  scoredFactors: number; factorCount: number;
  score: AnalysisDetail["scores"][number];
  relationship: AnalysisDetail["relationships"][number] | null;
}

export interface OpportunityView {
  analysis: Analysis; dataOrigin: "synthetic" | "collected"; completeness: Completeness;
  ranking: RankingRow[];
  claims: Map<string, Conclusion>;
  uncertainties: Map<string, AnalysisDetail["uncertainties"][number]>;
  source: (id: string) => ResolvedSource;
  companyName: (id: string) => string;
}

/** Analyses that have scores, newest first (the opportunities page can switch between them). */
export function getScoredAnalyses(b: Bundle = bundle): Analysis[] {
  return b.analyses.filter((a) => a.detail.scores.length > 0).sort((x, y) => y.generatedAt.localeCompare(x.generatedAt));
}

/** 商機分析 (W2-04): ranking, score breakdown, relationship classes and citations for one analysis. */
export function getOpportunityView(analysisId?: string | null, b: Bundle = bundle): OpportunityView | null {
  const list = getScoredAnalyses(b);
  const a = list.find((x) => x.analysisId === analysisId) ?? list[0];
  if (!a) return null;
  const ds = b.datasets[a.inputDatasetId];
  const names = new Map(ds.companies.map((c) => [c.companyId, c.name]));
  const companyName = (id: string) => names.get(id) ?? id;
  const rel = new Map(a.detail.relationships.map((r) => [r.companyId, r]));
  const ranking = a.detail.scores
    .filter((s) => s.subject.entity_type === "company")
    .map((s) => ({
      key: s.scoreId, rank: s.rank, companyId: s.subject.entity_id, companyName: companyName(s.subject.entity_id), total: s.total, max: s.max,
      scoredFactors: s.factors.filter((f) => f.status === "scored").length, factorCount: s.factors.length, score: s,
      relationship: rel.get(s.subject.entity_id) ?? null,
    }))
    .sort((x, y) => (x.rank ?? Infinity) - (y.rank ?? Infinity) || y.total - x.total);
  return {
    analysis: a, dataOrigin: a.dataOrigin, completeness: ds.completeness, ranking,
    claims: new Map(a.detail.conclusions.map((c) => [c.claimId, c])),
    uncertainties: new Map(a.detail.uncertainties.map((u) => [u.uncertaintyId, u])),
    source: (id) => ds.sources[id] ?? { sourceId: id, missing: true as const },
    companyName,
  };
}

export interface ExhibitionRow {
  exhibitionId: string; name: string; country: string | null; website: string | null; years: number[];
  acquisition: Bundle["exhibitions"][number]["acquisition"];
  latestCompleteness: Completeness | null; hasPackage: boolean;
  editions: EditionRow[];
}

/** Registered exhibitions from the dataset index (W2-01); nothing is hard-coded. */
export function getExhibitionRows(b: Bundle = bundle): ExhibitionRow[] {
  const editions = getOverview(b).editions;
  return b.exhibitions.map((ex) => {
    const eds = editions.filter((e) => e.exhibitionId === ex.exhibitionId).sort((x, y) => y.year - x.year);
    const latest = eds.find((e) => e.latest)?.latest ?? null;
    return {
      exhibitionId: ex.exhibitionId, name: ex.name, country: ex.country, website: ex.website, years: eds.map((e) => e.year),
      acquisition: ex.acquisition, latestCompleteness: latest?.completeness ?? null, hasPackage: !!latest, editions: eds,
    };
  });
}

export function matchesExhibition(r: ExhibitionRow, q: string): boolean {
  const s = q.trim().toLowerCase();
  return !s || [r.name, r.exhibitionId, r.country ?? "", ...r.years.map(String)].some((v) => v.toLowerCase().includes(s));
}
