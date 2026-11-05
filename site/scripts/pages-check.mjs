// W4-06: gate for the public GitHub Pages build (GitHub Pages is PUBLIC; CLAUDE.md: never publish private intelligence).
// Allowed only when every dataset and analysis in the bundle is synthetic, unless the project owner explicitly sets
// PAGES_ALLOW_COLLECTED=1 for approved, non-confidential real data. Also requires the security scan to pass.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
export function pagesProblems(bundle, allowCollected = false) {
  const problems = [];
  const real = [...Object.values(bundle.datasets).filter((d) => d.dataOrigin !== "synthetic").map((d) => d.datasetId),
    ...bundle.analyses.filter((a) => a.dataOrigin !== "synthetic").map((a) => a.analysisId)];
  if (real.length && !allowCollected) problems.push(`real (collected) data would become public: ${real.join(", ")} — needs the project owner's approval (PAGES_ALLOW_COLLECTED=1)`);
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const file = join(SITE, "dist-single", "index.html");
  if (!existsSync(file)) { console.error("pages-check: run `npm run build:single` first"); process.exit(2); }
  const bundle = JSON.parse(readFileSync(join(SITE, "src", "generated", "bundle.json"), "utf8"));
  const problems = pagesProblems(bundle, process.env.PAGES_ALLOW_COLLECTED === "1");
  if (problems.length) { console.error("pages-check FAILED:\n" + problems.join("\n")); process.exit(1); }
  execFileSync("node", [join(SITE, "scripts", "security-check.mjs")], { stdio: "inherit" });
  console.log(`pages-check: OK (data origin: ${bundle.dataOrigin}) → dist-single/index.html may be published`);
}
