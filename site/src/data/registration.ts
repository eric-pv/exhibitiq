import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import type { Bundle } from "./types";
import { bundle } from "./repository";

/**
 * W3-07 新增展覽 (A1-10 exhibition_registration). The static site only PREPARES the registration: it never writes
 * to GitHub and holds no credentials. The D2-13 workflow assigns the final exhibition_id, checks duplicates and
 * opens a data-update PR. Until that workflow exists, ADD_EXHIBITION_WORKFLOW stays null and the page says so.
 */
export const REPO_URL = "https://github.com/eric-pv/exhibitiq";
/** File name of the D2-13 workflow under .github/workflows/ once data engineering has merged it (proposed in Issue #90). */
export const ADD_EXHIBITION_WORKFLOW: string | null = null;
/** Where a user uploads an exhibitor list that could not be acquired automatically (Eric 2026-11-09; imported by data engineering). */
export const uploadUrl = (exhibitionId: string, year: number) => `${REPO_URL}/upload/dev/data-platform/data/uploads/${encodeURIComponent(exhibitionId)}/${year}`;
export const workflowUrl = (file: string | null = ADD_EXHIBITION_WORKFLOW) => (file ? `${REPO_URL}/actions/workflows/${file}` : null);

export interface RegistrationInput {
  name: string; nameZhHant?: string; nameEn?: string; country?: string; website?: string; years: number[]; requestedBy: string; exhibitionId?: string;
}

const ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const slug = (s: string) => s.normalize("NFKD").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^[^a-z]+/, "").replace(/-+$/, "").slice(0, 40).replace(/-+$/, "");
const host = (url?: string) => { try { return url ? new URL(url).hostname.replace(/^www\./, "") : ""; } catch { return ""; } };
const normName = (s: string) => s.normalize("NFKC").toLowerCase().replace(/[\s\p{P}\p{S}]+/gu, "");

/** Proposed id: English name, then name, then the website's first host label; a numeric suffix if it is taken. */
export function proposeId(input: Pick<RegistrationInput, "name" | "nameEn" | "website">, taken: Iterable<string>): string | null {
  const base = [input.nameEn ?? "", input.name, host(input.website).split(".")[0] ?? ""].map(slug).find((s) => ID.test(s));
  if (!base) return null;
  const used = new Set(taken);
  if (!used.has(base)) return base;
  for (let i = 2; ; i++) { const id = `${base.slice(0, 40 - String(i).length - 1)}-${i}`; if (!used.has(id)) return id; }
}

/** Registered exhibitions that look like the same one (same id, same normalised name, or same website host). */
export function possibleDuplicates(input: RegistrationInput, b: Bundle = bundle) {
  const n = [input.name, input.nameZhHant, input.nameEn].filter(Boolean).map((x) => normName(x!));
  const h = host(input.website);
  return b.exhibitions.filter((e) => e.exhibitionId === input.exhibitionId || n.includes(normName(e.name)) || (h && host(e.website ?? undefined) === h))
    .map((e) => ({ exhibitionId: e.exhibitionId, name: e.name }));
}

export function buildRegistration(input: RegistrationInput, now: Date, b: Bundle = bundle) {
  const opt = (v?: string) => (v && v.trim() ? v.trim() : undefined);
  const doc: Record<string, unknown> = {
    schema_version: b.schemaVersion,
    exhibition_id: input.exhibitionId,
    name: input.name.trim(),
    name_zh_hant: opt(input.nameZhHant), name_en: opt(input.nameEn),
    country: opt(input.country)?.toUpperCase(), website: opt(input.website),
    years: [...new Set(input.years)].sort((x, y) => x - y),
    registration_status: "requested",
    requested_by: input.requestedBy.trim(),
    requested_at: now.toISOString().replace(/\.\d{3}Z$/, "Z"),
    request_channel: "dashboard_form",
  };
  return Object.fromEntries(Object.entries(doc).filter(([, v]) => v !== undefined));
}

type Validate = ((d: unknown) => boolean) & { errors?: { instancePath: string; message?: string }[] | null };
let validator: Validate | null = null;
/** Same JSON Schema as tests/contract/registry_check.py (RG1); empty list = valid. */
export function validateRegistration(doc: unknown, b: Bundle = bundle): string[] {
  if (!validator) {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    addFormats(ajv);
    for (const s of Object.values(b.settings.schemas)) ajv.addSchema(s);
    validator = ajv.getSchema("https://exhibitiq.invalid/schemas/v1/exhibition_registration.schema.json") as unknown as Validate;
  }
  return validator!(doc) ? [] : (validator!.errors ?? []).map((e) => `${e.instancePath || "/"} ${e.message ?? ""}`);
}

/** Inputs for the D2-13 workflow_dispatch form (names as proposed in Issue #90). */
export function workflowInputs(doc: Record<string, unknown>) {
  return [["name", doc.name], ["years", (doc.years as number[]).join(",")], ["country", doc.country], ["website", doc.website],
    ["name_zh_hant", doc.name_zh_hant], ["name_en", doc.name_en], ["requested_by", doc.requested_by]]
    .filter(([, v]) => v !== undefined && v !== "") as [string, string][];
}
