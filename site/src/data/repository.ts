import bundleJson from "../generated/bundle.json";
import type { AnalysisDetail, Bundle, Completeness, EntityRef, FieldSources, SourceInfo } from "./types";

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

  const sortedAnalyses = [...b.analyses].sort((x, y) => y.generatedAt.localeCompare(x.generatedAt) || y.analysisId.localeCompare(x.analysisId));
  return {
    dataOrigin: b.dataOrigin,
    exhibitionCount: b.exhibitions.length,
    companyCount: companyIds.size,
    companyCompleteness: combineCompleteness(latest.map((d) => d.completeness)),
    analyzedCompanyCount: new Set(b.analyses.flatMap((a) => a.analyzedCompanyIds)).size,
    // re-analyses of the same package (other profiles/modes) must not be double-counted: latest analysis per package
    highPriorityCount: [...new Map([...sortedAnalyses].reverse().map((a) => [a.inputDatasetId, a] as const)).values()].reduce((n, a) => n + a.highPriorityRecommendations, 0),
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

/**
 * CSV for Excel (W3-05): UTF-8 BOM (Chinese text), CRLF rows, RFC 4180 quoting. Text cells that start with
 * = + - @ (or tab/CR) are prefixed with ' so Excel never runs them as formulas (CSV injection); numbers stay numbers.
 */
export function toCsv(headers: readonly string[], rows: (string | number | null)[][]): string {
  const esc = (v: string | number | null) => {
    let s = v === null ? "" : String(v);
    if (typeof v === "string" && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
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
  analysis: Analysis; dataOrigin: "synthetic" | "collected"; completeness: Completeness; exhibitionId: string;
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
  return a ? getAnalysisView(a, b) : null;
}

/** All analyses, newest first (報告中心). */
export function getAnalyses(b: Bundle = bundle): Analysis[] {
  return [...b.analyses].sort((x, y) => y.generatedAt.localeCompare(x.generatedAt));
}

/** The view model of one analysis; used by the opportunities page and ReportViewer (same data, same labels). */
export function getAnalysisView(a: Analysis, b: Bundle = bundle): OpportunityView {
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
    analysis: a, dataOrigin: a.dataOrigin, completeness: ds.completeness, ranking, exhibitionId: ds.exhibitionId,
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

export interface ComparisonColumn {
  editionId: string; exhibitionId: string; label: string; year: number;
  dataset: Bundle["datasets"][string] | null;
  lastAcquisition: EditionRow["lastAcquisition"];
  companyCount: number | null; listedParticipations: number | null; topCountries: { name: string; value: number }[];
  analysisCount: number;
  keywords: Record<string, { count: number; share: number | null; sourceIds: string[] }>;
}

/**
 * W3-01: the same metrics side by side for any selected editions (no exhibition hard-coded). Editions without a
 * validated package show null (資料不足). Keyword counts are candidates from the selected profile; shares only when complete.
 */
export function getComparison(editionIds: string[], profileId: string | null, b: Bundle = bundle) {
  const rows = getOverview(b).editions;
  const profile = b.settings.profiles.find((p) => p.profile.profile_id === profileId)?.profile ?? null;
  const kws = profile ? profile.keywords.filter((k) => k.enabled) : [];
  const columns: ComparisonColumn[] = editionIds.map((id) => rows.find((r) => r.editionId === id)).filter((r): r is EditionRow => !!r).map((r) => {
    const ds = r.latest ? b.datasets[r.latest.datasetId] ?? null : null;
    const countries = new Map<string, number>();
    for (const c of ds?.companies ?? []) countries.set(c.country ?? "未知", (countries.get(c.country ?? "未知") ?? 0) + 1);
    const complete = ds?.completeness.status === "complete";
    const n = ds?.companies.length ?? 0;
    return {
      editionId: r.editionId, exhibitionId: r.exhibitionId, label: `${r.exhibitionName}（${r.year}）`, year: r.year, dataset: ds,
      lastAcquisition: r.lastAcquisition, companyCount: ds ? n : null, listedParticipations: ds ? ds.listedParticipations : null,
      topCountries: [...countries].map(([name, value]) => ({ name, value })).sort((x, y) => y.value - x.value).slice(0, 3),
      analysisCount: ds ? b.analyses.filter((a) => a.inputDatasetId === ds.datasetId).length : 0,
      keywords: Object.fromEntries(kws.map((k) => {
        const m = ds && profile ? ds.keywordMatches[profile.profile_id]?.[k.term_id] : undefined;
        const count = m?.companyIds.length ?? 0;
        return [k.term_id, { count, share: complete && n ? count / n : null, sourceIds: m?.sourceIds ?? [] }];
      })),
    };
  });
  return { columns, profile, keywords: kws, editions: rows };
}

/** 資料及系統狀態 (W2-05): acquisition, validation, completeness, errors and warnings from the dataset index. */
export function getSystemStatus(b: Bundle = bundle) {
  const editions = getOverview(b).editions;
  const datasets = b.exhibitions.flatMap((ex) => ex.editions.flatMap((ed) => ed.datasets.map((d) => ({ ...d, exhibitionName: ex.name, year: ed.year, editionId: ed.editionId }))))
    .sort((x, y) => y.createdAt.localeCompare(x.createdAt));
  const count = <T,>(xs: T[], f: (x: T) => string) => xs.reduce<Record<string, number>>((m, x) => ({ ...m, [f(x)]: (m[f(x)] ?? 0) + 1 }), {});
  return {
    editions, datasets,
    acquisition: count(editions, (e) => e.lastAcquisition?.status ?? "none"),
    validation: count(datasets, (d) => d.validation),
    acquisitionErrors: editions.reduce((n, e) => n + (e.lastAcquisition?.errorCount ?? 0), 0),
    notices: [...b.notices].sort((x, y) => y.occurredAt.localeCompare(x.occurredAt)),
    noticeLevels: count(b.notices, (n) => n.level),
    source: { ...b.generatedFrom, schemaVersion: b.schemaVersion, indexGeneratedAt: b.indexGeneratedAt },
  };
}

/** W3-03: approved BXR product cards (only approved ones are shown) and the AI recommendations that cite them. */
export function getProducts(b: Bundle = bundle) {
  const products = b.settings.products.filter((p) => p.approvalStatus === "approved");
  const recs = b.analyses.flatMap((a) => a.detail.recommendations.filter((r) => r.productIds.length > 0).map((r) => ({ ...r, analysis: a })));
  return products.map((p) => ({
    ...p, termLabels: p.terms.map((t) => b.settings.termLabels[t] ?? t),
    recommendations: recs.filter((r) => r.productIds.includes(p.productId)),
  }));
}

export interface HistoryStep {
  fromYear: number; toYear: number; returning: number;
  /** null = cannot be known: the earlier (new) or later (not seen again) year is incomplete — never estimated. */
  newCount: number | null; notSeenAgain: number | null;
}

/** 歷史趨勢 (W3-02, same rules as A3-04 `profile_tools.history`): one exhibition, latest package per year, oldest first. */
export function getHistory(exhibitionId: string, profileId: string | null, b: Bundle = bundle) {
  const profile = b.settings.profiles.find((p) => p.profile.profile_id === profileId)?.profile ?? null;
  const kws = profile ? profile.keywords.filter((k) => k.enabled) : [];
  const years = getOverview(b).editions.filter((e) => e.exhibitionId === exhibitionId && e.latest && b.datasets[e.latest.datasetId])
    .sort((x, y) => x.year - y.year).map((e) => {
      const ds = b.datasets[e.latest!.datasetId];
      const ids = new Set(ds.companies.map((c) => c.companyId));
      const complete = ds.completeness.status === "complete";
      return {
        year: e.year, datasetId: ds.datasetId, completeness: ds.completeness, complete, companyIds: ids, companyCount: ids.size,
        keywords: Object.fromEntries(kws.map((k) => {
          const n = (profile && ds.keywordMatches[profile.profile_id]?.[k.term_id]?.companyIds.length) ?? 0;
          return [k.term_id, { count: n, share: complete && ids.size ? n / ids.size : null }];
        })),
      };
    });
  const steps: HistoryStep[] = years.slice(1).map((cur, i) => {
    const prev = years[i];
    const returning = [...cur.companyIds].filter((c) => prev.companyIds.has(c)).length;
    return {
      fromYear: prev.year, toYear: cur.year, returning,
      newCount: prev.complete ? cur.companyCount - returning : null,
      notSeenAgain: cur.complete ? prev.companyCount - returning : null,
    };
  });
  return { status: years.length >= 2 ? "ok" as const : "insufficient" as const, years, steps, keywords: kws, profile };
}

const KF_COMPLETENESS: Record<string, string> = { complete: "完整", partial: "不完整", unknown: "未知" };
const KF_REL: Record<string, string> = { potential_customer: "潛在客戶", competitor: "競爭對手", partner: "合作夥伴", channel: "通路", unrelated: "不相關", unknown: "未知" };
const byCount = (x: [string, number], y: [string, number]) => y[1] - x[1] || (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0);

/**
 * 數據摘要 (A3-02): the same lines as the Markdown report's key_figure_lines() (exhibitiq_tools.py), computed only
 * from the analysis and its package; reports.test.tsx checks they are identical. Also returns the country chart data.
 */
export function keyFigures(a: Analysis, b: Bundle = bundle) {
  const ds = b.datasets[a.inputDatasetId];
  const count = (xs: string[]) => [...xs.reduce((m, x) => m.set(x, (m.get(x) ?? 0) + 1), new Map<string, number>())].sort(byCount);
  const countries = count(ds.companies.map((c) => c.country ?? "未知")).slice(0, 5);
  const rels = count(a.detail.relationships.map((r) => r.type));
  const pri = (["high", "medium", "low"] as const).map((k) => [k, a.detail.recommendations.filter((r) => r.priority === k).length] as const);
  const scored = a.detail.scores.filter((s) => s.subject.entity_type === "company");
  const best = scored.reduce<(typeof scored)[number] | null>((m, s) => (!m || s.total > m.total ? s : m), null);
  const level: Record<string, string> = { high: "高", medium: "中", low: "低" };
  const c = ds.completeness;
  const lines = [
    `已取得企業：${ds.companies.length} 家（完整度：${KF_COMPLETENESS[c.status] ?? c.status}；官方公布參展商：${c.official ?? "未知"}）`,
    `主要國家／地區（只計已取得企業）：${countries.map(([k, v]) => `${k} ${v}`).join("、") || "無"}`,
    `列於名單的參展紀錄：${ds.listedParticipations} 筆`,
    `關係候選（AI 推論）：${rels.map(([k, v]) => `${KF_REL[k] ?? k} ${v}`).join("、") || "無"}`,
    `建議（AI 推論）：${pri.map(([k, v]) => `優先度${level[k]} ${v}`).join("、")}`,
    `已評分企業（AI 推論）：${scored.length} 家${best ? `；最高 ${best.total}／${best.max} 分` : ""}`,
    ...(c.status !== "complete" ? ["資料不完整：以上數字只代表實際取得的部分，不計算比例"] : []),
  ];
  return { lines, countries: countries.map(([name, value]) => ({ name, value })) };
}

/**
 * W3-06: every analysis that mentions one company (score, relationship candidate, conclusion or recommendation subject),
 * so the company page can link to the opportunity view and the report. Everything listed is AI output.
 */
export function getCompanyAnalyses(companyId: string, b: Bundle = bundle) {
  const isMe = (e: EntityRef) => e.entity_type === "company" && e.entity_id === companyId;
  return getAnalyses(b).map((a) => {
    const d = a.detail;
    const score = d.scores.find((s) => isMe(s.subject)) ?? null;
    return {
      analysisId: a.analysisId, title: a.title, generatedAt: a.generatedAt, reviewStatus: a.reviewStatus,
      score: score ? { rank: score.rank, total: score.total, max: score.max } : null,
      relationships: d.relationships.filter((r) => r.companyId === companyId).map((r) => r.type),
      conclusions: d.conclusions.filter((c) => c.subjects.some(isMe)).length,
      recommendations: d.recommendations.filter((r) => r.subjects.some(isMe)).length,
    };
  }).filter((x) => x.score || x.relationships.length || x.conclusions || x.recommendations);
}

/**
 * Eric 2026-11-09: the exhibition list shows whether an exhibitor list was obtained and, when not, why (from the
 * dataset index: assessment notes, then the latest acquisition note) and that the user can upload the list.
 */
export function listStatus(r: ExhibitionRow): { obtained: boolean; reason: string | null } {
  if (r.hasPackage) return { obtained: true, reason: null };
  const lastNote = r.editions.map((e) => e.lastAcquisition?.notes).find((n) => !!n) ?? null;
  return { obtained: false, reason: r.acquisition.notes ?? lastNote };
}
