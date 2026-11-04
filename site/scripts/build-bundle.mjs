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
        companies.forEach((c, i) => v.check("company", c, `${where}/companies.jsonl:${i + 1}`));
        participations.forEach((p, i) => v.check("participation", p, `${where}/participations.jsonl:${i + 1}`));
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
            };
          }),
          listedParticipations: participations.filter((p) => p.listing_status === "listed").length,
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
      analyses.push({
        analysisId: a.analysis_id, title: a.title, analysisType: a.analysis_type, inputDatasetId: a.input_dataset_id,
        generatedAt: a.generated_at, reviewStatus: a.review_status, dataOrigin: a.data_origin,
        analyzedCompanyIds: [...new Set((a.scores ?? []).filter((s) => s.subject.entity_type === "company").map((s) => s.subject.entity_id))],
        highPriorityRecommendations: a.recommendations.filter((r) => r.priority === "high").length,
        claimCounts: a.conclusions.reduce((acc, c) => ({ ...acc, [c.claim_type]: (acc[c.claim_type] ?? 0) + 1 }), {}),
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
