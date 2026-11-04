import { readFileSync } from "node:fs";
import { join } from "node:path";
// @ts-expect-error plain ESM build script without type declarations
import { buildBundle, REPO } from "../scripts/build-bundle.mjs";
import { getOverview } from "./data/repository";
import type { Bundle } from "./data/types";

// A2-02: the Dashboard must show exactly the expected numbers for the golden sample.
test("golden sample: overview matches data/samples/golden/v1/expected/overview.json", () => {
  const g = join(REPO, "data", "samples", "golden", "v1");
  const o = getOverview(buildBundle({ indexPath: join(g, "dataset_index.json"), analysesDir: join(g, "expected", "analysis") }) as Bundle);
  const expected = JSON.parse(readFileSync(join(g, "expected", "overview.json"), "utf8"));
  for (const [k, v] of Object.entries(expected)) expect((o as Record<string, unknown>)[k], k).toEqual(v);
});
