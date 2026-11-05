// @ts-expect-error plain ESM script without type declarations
import { pagesProblems } from "../scripts/pages-check.mjs";
import { bundle } from "./data/repository";

test("public Pages build: synthetic data passes, real data is blocked unless the owner allows it", () => {
  expect(pagesProblems(bundle)).toEqual([]); // current bundle is synthetic
  const d = Object.values(bundle.datasets)[0];
  const real = { ...bundle, datasets: { [d.datasetId]: { ...d, dataOrigin: "collected" } } };
  expect(pagesProblems(real)[0]).toMatch(/would become public/);
  expect(pagesProblems(real, true)).toEqual([]);
});
