// W4-05: checks the built site (dist/, dist-single/) and site/src for anything that must never ship to a browser.
// Run after `npm run build` / `npm run build:single`: `node scripts/security-check.mjs`. Exit 1 on any finding.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
export const RULES = [
  ["GitHub token", /\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b/],
  ["Anthropic/OpenAI key", /\bsk-(ant-)?[A-Za-z0-9_-]{20,}\b/],
  ["AWS access key", /\bAKIA[0-9A-Z]{16}\b/],
  ["Google API key", /\bAIza[0-9A-Za-z_-]{35}\b/],
  ["Slack token", /\bxox[abprs]-[A-Za-z0-9-]{10,}\b/],
  ["private key", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["bearer credential", /\bBearer\s+[A-Za-z0-9._-]{20,}/],
  // the static site must not call write APIs or an LLM (spec §4.1)
  ["GitHub API call", /api\.github\.com/],
  ["LLM API call", /api\.anthropic\.com|api\.openai\.com/],
];

export function scanText(text) {
  return RULES.filter(([, re]) => re.test(text)).map(([name]) => name);
}

function walk(dir) {
  return readdirSync(dir).flatMap((f) => { const p = join(dir, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const targets = ["dist", "dist-single", "src"].map((d) => join(SITE, d)).filter(existsSync);
  if (!targets.some((t) => t.endsWith("dist") || t.endsWith("dist-single"))) { console.error("security-check: build first (npm run build)"); process.exit(2); }
  const findings = [];
  for (const t of targets) for (const f of walk(t)) {
    if (!/\.(html|js|css|json|ts|tsx|map|txt)$/.test(f) || /\.test\.tsx?$/.test(f)) continue;
    for (const name of scanText(readFileSync(f, "utf8"))) findings.push(`${relative(SITE, f)}: ${name}`);
  }
  if (findings.length) { console.error("security-check FAILED:\n" + findings.join("\n")); process.exit(1); }
  console.log(`security-check: OK (${targets.map((t) => relative(SITE, t)).join(", ")})`);
}
