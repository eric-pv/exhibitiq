// Builds site/src/generated/bundle.json — the Dashboard's internal view model.
// Deterministic (no AI). Every input is validated against schemas/v1 first;
// any invalid input stops the build (DEVELOPMENT_PLAN.md §3).
//
// Inputs (repo-relative):
//   dataset index   data/index/datasets.json, else schemas/v1/examples/index/dataset_index.example.json
//   analyses        reports/analysis/**/*.json, else schemas/v1/examples/analysis/*.json
// Override with BUNDLE_INDEX=<path> and BUNDLE_ANALYSES=<dir>.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO = resolve(HERE, "..", "..");
const SCHEMAS = join(REPO, "schemas", "v1");

function readJson(p) { return JSON.parse(readFileSync(p, "utf8")); }
function readJsonl(p) {
  const text = readFileSync(p, "utf8");
  return text.split("\n").filter((l) => l.length > 0).map((l) => JSON.parse(l));
}
function walkJson(dir) {
  const out = [];
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) out.push(...walkJson(p)); else if (f.endsWith(".json")) out.push(p);
  }
  return out.sort();
}

export function loadValidators() {
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  for (const f of readdirSync(SCHEMAS).filter((f) => f.endsWith(".schema.json"))) ajv.addSchema(readJson(join(SCHEMAS, f)));
  const get = (name) => {
    const v = ajv.getSchema(`https://exhibitiq.invalid/schemas/v1/${name}.schema.json`);
    if (!v) throw new Error(`schema not found: ${name}`);
    return v;
  };
  return {
    version: readFileSync(join(SCHEMAS, "VERSION"), "utf8").trim(),
    check(name, value, where) {
      const v = get(name);
      if (!v(value)) throw new Error(`${where}: does not match ${name}.schema.json: ${ajv.errorsText(v.errors)}`);
    },
  };
}

function defaultIndex() {
  const real = join(REPO, "data", "index", "datasets.json");
  return existsSync(real) ? real : join(SCHEMAS, "examples", "index", "dataset_index.example.json");
}
function defaultAnalyses() {
  const real = join(REPO, "reports", "analysis");
  return existsSync(real) ? real : join(SCHEMAS, "examples", "analysis");
}

export function buildBundle({ indexPath = defaultIndex(), analysesDir = defaultAnalyses() } = {}) {
  const v = loadValidators();
  const index = readJson(indexPath);
  v.check("dataset_index", index, relative(REPO, indexPath));

  const datasets = {};
  const exhibitions = index.exhibitions.map((ex) => ({
    exhibitionId: ex.exhibition_id,
    name: ex.name_zh_hant ?? ex.name,
    country: ex.country ?? null,
    acquisition: { method: ex.acquisition.method, status: ex.acquisition.status, notes: ex.acquisition.notes ?? null },
    editions: ex.editions.map((ed) => {
      for (const ds of ed.datasets) {
        if (ds.dataset_id !== ed.latest_dataset_id) continue; // the Dashboard shows the latest validated package
        if (ds.location.storage !== "git") throw new Error(`${ds.dataset_id}: only git-stored packages are supported in Phase 1`);
        const pkg = join(REPO, ds.location.locator);
        const where = relative(REPO, pkg);
        const manifest = readJson(join(pkg, "manifest.json"));
        v.check("manifest", manifest, `${where}/manifest.json`);
        if (manifest.schema_version !== v.version) throw new Error(`${where}: schema_version ${manifest.schema_version} != ${v.version}`);
        if (manifest.content_hash !== ds.content_hash) throw new Error(`${where}: content_hash differs from the dataset index`);
        const companies = readJsonl(join(pkg, "companies.jsonl"));
        const participations = readJsonl(join(pkg, "participations.jsonl"));
        const sourceRecords = readJsonl(join(pkg, "sources.jsonl"));
        companies.forEach((c, i) => v.check("company", c, `${where}/companies.jsonl:${i + 1}`));
        participations.forEach((p, i) => v.check("participation", p, `${where}/participations.jsonl:${i + 1}`));
        sourceRecords.forEach((s, i) => v.check("source", s, `${where}/sources.jsonl:${i + 1}`));
        const sources = Object.fromEntries(sourceRecords.map((s) => [s.source_id, {
          sourceId: s.source_id, sourceType: s.source_type, url: s.url ?? null, title: s.title ?? null, publisher: s.publisher ?? null,
          retrievedAt: s.retrieved_at, crawlRunId: s.crawl_run_id ?? null, contentSha256: s.content_sha256,
          snapshot: { storage: s.snapshot.storage, locator: s.snapshot.locator ?? null, retainedUntil: s.snapshot.retained_until ?? null },
          notes: s.notes ?? null,
        }]));
        // Every cited source must exist in the package: the detail page shows each field's source (W2-03).
        const cite = (ids, what) => { for (const id of ids ?? []) if (!sources[id]) throw new Error(`${where}: ${what} cites ${id}, which is not in sources.jsonl`); };
        const citeRecord = (r, what) => {
          cite(r.source_ids, what);
          for (const ids of Object.values(r.field_sources ?? {})) cite(ids, what);
          for (const a of r.aliases ?? []) cite(a.source_ids, what);
        };
        companies.forEach((c) => citeRecord(c, c.company_id));
        participations.forEach((p) => citeRecord(p, p.participation_id));
        datasets[ds.dataset_id] = {
          datasetId: ds.dataset_id,
          exhibitionId: ex.exhibition_id,
          editionId: ed.edition_id,
          dataOrigin: manifest.data_origin,
          createdAt: manifest.created_at,
          completeness: {
            status: manifest.completeness_status,
            official: manifest.completeness.official_exhibitor_count,
            collected: manifest.completeness.collected_participation_count,
          },
          companies: companies.map((c) => {
            const ps = participations.filter((p) => p.company_id === c.company_id);
            return {
              companyId: c.company_id, name: c.name, country: c.country ?? null, verificationStatus: c.verification_status,
              aliases: (c.aliases ?? []).map((a) => a.name),
              listed: ps.some((p) => p.listing_status === "listed"),
              booths: [...new Set(ps.map((p) => p.booth).filter(Boolean))],
              detail: {
                nameEn: c.name_en ?? null, nameZhHant: c.name_zh_hant ?? null, website: c.website ?? null, domains: c.domains ?? [],
                description: c.description ?? null, status: c.status, mergedInto: c.merged_into ?? null, firstSeenAt: c.first_seen_at ?? null,
                notes: c.notes ?? null, sourceIds: c.source_ids, fieldSources: c.field_sources ?? {},
                aliases: (c.aliases ?? []).map((a) => ({ name: a.name, lang: a.lang ?? null, sourceIds: a.source_ids })),
                participations: ps.map((p) => ({
                  participationId: p.participation_id, editionId: p.edition_id, nameAsListed: p.exhibitor_name_as_listed,
                  participationType: p.participation_type, listingStatus: p.listing_status, booth: p.booth ?? null, hall: p.hall ?? null,
                  countryAsListed: p.country_as_listed ?? null, websiteAsListed: p.website_as_listed ?? null,
                  categories: p.categories_as_listed ?? [], products: p.products_as_listed ?? [],
                  firstSeenAt: p.first_seen_at ?? null, lastSeenAt: p.last_seen_at ?? null, verificationStatus: p.verification_status,
                  sourceIds: p.source_ids, fieldSources: p.field_sources ?? {}, notes: p.notes ?? null,
                })),
              },
            };
          }),
          listedParticipations: participations.filter((p) => p.listing_status === "listed").length,
          sources,
        };
      }
      return {
        editionId: ed.edition_id,
        year: ed.year,
        latestDatasetId: ed.latest_dataset_id,
        lastAcquisition: ed.last_acquisition
          ? { method: ed.last_acquisition.method, status: ed.last_acquisition.status, finishedAt: ed.last_acquisition.finished_at, notes: ed.last_acquisition.notes ?? null }
          : null,
        datasets: ed.datasets.map((ds) => ({
          datasetId: ds.dataset_id, dataOrigin: ds.data_origin, validation: ds.validation.status,
          completeness: { status: ds.completeness_status, official: ds.official_exhibitor_count, collected: ds.collected_participation_count },
        })),
      };
    }),
  }));

  const analyses = [];
  if (existsSync(analysesDir)) {
    for (const f of walkJson(analysesDir)) {
      const a = readJson(f);
      v.check("analysis_result", a, relative(REPO, f));
      if (!datasets[a.input_dataset_id]) continue; // analysis of a package that is not the latest one
      const ds = datasets[a.input_dataset_id];
      // Every source an analysis cites must exist in its input package (W2-04: citations are clickable).
      const cited = [
        ...(a.evidence_source_ids ?? []),
        ...a.conclusions.flatMap((c) => c.evidence_source_ids ?? []),
        ...(a.scores ?? []).flatMap((s) => s.factors.flatMap((f) => f.evidence_source_ids ?? [])),
        ...(a.relationships ?? []).flatMap((r) => r.evidence_source_ids ?? []),
        ...a.recommendations.flatMap((r) => r.evidence_source_ids ?? []),
      ];
      for (const id of cited) if (!ds.sources[id]) throw new Error(`${relative(REPO, f)}: cites ${id}, which is not in ${a.input_dataset_id}/sources.jsonl`);
      analyses.push({
        analysisId: a.analysis_id, title: a.title, analysisType: a.analysis_type, inputDatasetId: a.input_dataset_id,
        generatedAt: a.generated_at, reviewStatus: a.review_status, dataOrigin: a.data_origin,
        analyzedCompanyIds: [...new Set((a.scores ?? []).filter((s) => s.subject.entity_type === "company").map((s) => s.subject.entity_id))],
        highPriorityRecommendations: a.recommendations.filter((r) => r.priority === "high").length,
        claimCounts: a.conclusions.reduce((acc, c) => ({ ...acc, [c.claim_type]: (acc[c.claim_type] ?? 0) + 1 }), {}),
        detail: {
          summary: a.summary ?? null, skillVersion: a.skill_version ?? null,
          conclusions: a.conclusions.map((c) => ({
            claimId: c.claim_id, claimType: c.claim_type, statement: c.statement, subjects: c.subjects ?? [],
            sourceIds: c.evidence_source_ids ?? [], verificationStatus: c.verification_status ?? null, confidence: c.confidence ?? null,
            rationale: c.rationale ?? null, missingData: c.missing_data ?? null, uncertaintyIds: c.uncertainty_ids ?? [],
          })),
          uncertainties: (a.uncertainties ?? []).map((u) => ({ uncertaintyId: u.uncertainty_id, description: u.description, impact: u.impact })),
          scores: (a.scores ?? []).map((s) => ({
            scoreId: s.score_id, modelId: s.score_model_id, subject: s.subject, total: s.total_points, max: s.max_total_points, rank: s.rank ?? null,
            factors: s.factors.map((x) => ({
              factorId: x.factor_id, label: x.label, status: x.status, points: x.points, max: x.max_points,
              sourceIds: x.evidence_source_ids ?? [], claimIds: x.claim_ids ?? [], rationale: x.rationale ?? null,
            })),
          })),
          relationships: (a.relationships ?? []).map((r) => ({
            relationshipId: r.relationship_id, companyId: r.company_id, type: r.relationship_type, rationale: r.rationale ?? null,
            confidence: r.confidence ?? null, sourceIds: r.evidence_source_ids ?? [], claimIds: r.claim_ids ?? [],
          })),
          recommendations: a.recommendations.map((r) => ({
            recommendationId: r.recommendation_id, type: r.recommendation_type, statement: r.statement, rationale: r.rationale ?? null,
            priority: r.priority, subjects: r.subjects ?? [], assumptions: r.assumptions ?? [], sourceIds: r.evidence_source_ids ?? [],
            claimIds: r.based_on_claim_ids ?? [], scoreIds: r.score_ids ?? [], uncertaintyIds: r.uncertainty_ids ?? [],
          })),
        },
      });
    }
  }

  const origins = new Set([
    ...Object.values(datasets).map((d) => d.dataOrigin),
    ...analyses.map((a) => a.dataOrigin),
  ]);
  return {
    schemaVersion: v.version,
    generatedFrom: { index: relative(REPO, indexPath), analyses: relative(REPO, analysesDir) },
    indexGeneratedAt: index.generated_at,
    dataOrigin: origins.size === 0 ? "none" : origins.has("synthetic") ? "synthetic" : "collected",
    exhibitions,
    datasets,
    analyses,
    notices: index.notices.map((n) => ({ level: n.level, message: n.message, occurredAt: n.occurred_at })),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const bundle = buildBundle({
      indexPath: process.env.BUNDLE_INDEX ? resolve(process.env.BUNDLE_INDEX) : undefined,
      analysesDir: process.env.BUNDLE_ANALYSES ? resolve(process.env.BUNDLE_ANALYSES) : undefined,
    });
    const out = join(HERE, "..", "src", "generated", "bundle.json");
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, JSON.stringify(bundle, null, 2) + "\n");
    console.log(`bundle: ${bundle.exhibitions.length} exhibitions, ${Object.keys(bundle.datasets).length} datasets, ${bundle.analyses.length} analyses (${bundle.dataOrigin}) ← ${bundle.generatedFrom.index}`);
  } catch (e) {
    console.error(`bundle build FAILED: ${e.message}`);
    process.exit(1);
  }
}
