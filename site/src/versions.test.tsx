import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import { getOverview, getSystemStatus } from "./data/repository";
import type { Bundle } from "./data/types";

/**
 * A4-06 (history): an edition with two package versions. The Dashboard analyses and shows the LATEST validated
 * version; the older version stays listed (with its own id, hash and validation) on the status page, so every
 * version remains traceable. Analyses of the older version are not mixed into the current view.
 */
test("two package versions of one edition: latest is shown, the older one stays traceable", () => {
  const g = JSON.parse(readFileSync(join(REPO, "data/samples/golden/v1/dataset_index.json"), "utf8"));
  const ed = g.exhibitions[0].editions[0];
  const v1 = ed.datasets[0];
  const v2 = { ...v1, dataset_id: `${v1.dataset_id.split(".")[0]}.20261110T000000Z`, created_at: "2026-11-10T00:00:00Z" };
  ed.datasets = [v1, v2];
  ed.latest_dataset_id = v2.dataset_id;
  const dir = mkdtempSync(join(tmpdir(), "ver-"));
  writeFileSync(join(dir, "index.json"), JSON.stringify(g));
  const b = buildBundle({ indexPath: join(dir, "index.json"), analysesDir: join(REPO, "data/samples/golden/v1/expected/analysis") }) as Bundle;

  expect(Object.keys(b.datasets)).toEqual([v2.dataset_id]); // only the latest version feeds the pages
  expect(getOverview(b).editions[0].latest?.datasetId).toBe(v2.dataset_id);
  const listed = getSystemStatus(b).datasets.map((d) => d.datasetId);
  expect(listed).toEqual(expect.arrayContaining([v1.dataset_id, v2.dataset_id])); // both versions traceable
  expect(b.analyses.every((a) => a.inputDatasetId === v2.dataset_id)).toBe(true); // v1 analyses not mixed in
});
