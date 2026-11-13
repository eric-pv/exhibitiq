/**
 * 分析設定 (W2-06): local drafts, submitted profiles and the versions used by analyses.
 * The browser never writes to GitHub and never runs analysis (docs/specs/analysis-profile-contract.md §6).
 */
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { bundle } from "./repository";
import type { AnalysisProfile, Bundle } from "./types";

// ---------------------------------------------------------------- canonical JSON + SHA-256 (sync, no WebCrypto needed)
export function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (v && typeof v === "object") return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonical((v as Record<string, unknown>)[k])}`).join(",")}}`;
  return JSON.stringify(v);
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
export function sha256Hex(text: string): string {
  const msg = new TextEncoder().encode(text);
  const len = ((msg.length + 9 + 63) >> 6) << 6;
  const buf = new Uint8Array(len); buf.set(msg); buf[msg.length] = 0x80;
  const bits = msg.length * 8, dv = new DataView(buf.buffer);
  dv.setUint32(len - 8, Math.floor(bits / 2 ** 32)); dv.setUint32(len - 4, bits >>> 0);
  const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const W = new Uint32Array(64);
  const r = (x: number, n: number) => (x >>> n) | (x << (32 - n));
  for (let o = 0; o < len; o += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(o + i * 4);
    for (let i = 16; i < 64; i++) W[i] = (r(W[i - 15], 7) ^ r(W[i - 15], 18) ^ (W[i - 15] >>> 3)) + W[i - 16] + (r(W[i - 2], 17) ^ r(W[i - 2], 19) ^ (W[i - 2] >>> 10)) + W[i - 7];
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (r(e, 6) ^ r(e, 11) ^ r(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + W[i]) >>> 0;
      const t2 = ((r(a, 2) ^ r(a, 13) ^ r(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
  }
  return [...H].map((x) => x.toString(16).padStart(8, "0")).join("");
}
export const profileHash = (p: AnalysisProfile) => "sha256:" + sha256Hex(canonical(p));

// ---------------------------------------------------------------- validation (same schema + rules as profile_check.py)
type Validate = ((d: unknown) => boolean) & { errors?: { instancePath: string; message?: string }[] | null };
let validator: Validate | null = null;
export function validateProfile(doc: unknown, b: Bundle = bundle): string[] {
  if (!validator) {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    addFormats(ajv);
    for (const s of Object.values(b.settings.schemas)) ajv.addSchema(s);
    validator = ajv.getSchema("https://exhibitiq.invalid/schemas/v1/analysis_profile.schema.json") as unknown as Validate;
  }
  if (!validator!(doc)) return (validator!.errors ?? []).map((e) => `${e.instancePath || "/"} ${e.message ?? ""}`);
  const p = doc as AnalysisProfile, errors: string[] = [];
  const ids = p.keywords.map((k) => k.term_id);
  if (new Set(ids).size !== ids.length) errors.push("關鍵字代碼（term_id）重複");
  const missing = (p.targets?.focus_term_ids ?? []).filter((x) => !ids.includes(x));
  if (missing.length) errors.push(`指定領域不在關鍵字中：${missing.join("、")}`);
  if (p.mode !== "bxr_opportunity" && p.targets?.bxr_product_ids?.length) errors.push("B、C 模式不能使用 BXR 產品卡");
  return errors;
}

// ---------------------------------------------------------------- local drafts (browser storage, per viewer)
const KEY = "exhibitiq.analysisProfiles.drafts.v1";
export type Drafts = Record<string, AnalysisProfile>;
export function loadDrafts(): Drafts {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? "{}"); return v && typeof v === "object" ? v : {}; } catch { return {}; }
}
export function saveDrafts(d: Drafts): boolean {
  try { localStorage.setItem(KEY, JSON.stringify(d)); return true; } catch { return false; }
}

// ---------------------------------------------------------------- the three states
export interface ProfileState {
  profileId: string; name: string;
  draft: AnalysisProfile | null; draftHash: string | null;
  submitted: AnalysisProfile | null; submittedHash: string | null;
  /** local draft exists and differs from the submitted version (or nothing is submitted) */
  unsubmitted: boolean;
  analyses: { analysisId: string; title: string; profileVersion: number; matchesSubmitted: boolean }[];
}
export function profileStates(drafts: Drafts, b: Bundle = bundle): ProfileState[] {
  const sub = new Map(b.settings.profiles.map((x) => [x.profile.profile_id, x]));
  const ids = [...new Set([...sub.keys(), ...Object.keys(drafts)])].sort();
  return ids.map((id) => {
    const s = sub.get(id) ?? null, d = drafts[id] ?? null;
    const dh = d ? profileHash(d) : null;
    return {
      profileId: id, name: (d ?? s!.profile).name, draft: d, draftHash: dh, submitted: s?.profile ?? null, submittedHash: s?.hash ?? null,
      unsubmitted: !!d && dh !== s?.hash,
      analyses: b.analyses.filter((a) => a.config?.profileId === id).map((a) => ({
        analysisId: a.analysisId, title: a.title, profileVersion: a.config!.profileVersion, matchesSubmitted: a.config!.profileHash === s?.hash,
      })),
    };
  });
}

/** The file to submit: version bumped when the content differs from the submitted version. */
export function forSubmission(draft: AnalysisProfile, submitted: AnalysisProfile | null, now = new Date()): AnalysisProfile {
  if (submitted && profileHash(draft) === profileHash(submitted)) return draft;
  return { ...draft, version: Math.max(draft.version, (submitted?.version ?? 0) + 1), updated_at: now.toISOString().replace(/\.\d+Z$/, "Z") };
}

export function blankProfile(id: string, name: string): AnalysisProfile {
  return { schema_version: bundle.schemaVersion, profile_id: id, version: 1, name, mode: "industry_research", keywords: [],
    relationship_signals: {}, updated_at: new Date().toISOString().replace(/\.\d+Z$/, "Z") };
}
export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || `profile-${Date.now().toString(36)}`;
