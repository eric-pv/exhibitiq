import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ErrorBoundary } from "./components/states/ErrorBoundary";
import { getAnalyses, getCompanyRows, getComparison, getExhibitionRows, getOpportunityView, getOverview, getSystemStatus } from "./data/repository";
import { bundle } from "./data/repository";
import type { Bundle } from "./data/types";

/** W4-03: an empty index (no exhibitions, packages or analyses) must give empty results, never a crash or invented numbers. */
const empty: Bundle = { ...bundle, exhibitions: [], datasets: {}, analyses: [], notices: [], dataOrigin: "none" };

test("no data: every repository view is empty, not invented", () => {
  const o = getOverview(empty);
  expect([o.exhibitionCount, o.companyCount, o.analyzedCompanyCount, o.highPriorityCount]).toEqual([0, 0, 0, 0]);
  expect(o.companyCompleteness).toBeNull();
  expect(o.latestAnalysis).toBeNull();
  expect(getCompanyRows(empty)).toEqual([]);
  expect(getExhibitionRows(empty)).toEqual([]);
  expect(getOpportunityView(null, empty)).toBeNull();
  expect(getAnalyses(empty)).toEqual([]);
  expect(getComparison([], null, empty).columns).toEqual([]);
  expect(getSystemStatus(empty).editions).toEqual([]);
});

test("a page that throws shows the unified error state", () => {
  const Boom = () => { throw new Error("資料格式錯誤"); };
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(<MemoryRouter><ErrorBoundary><Boom /></ErrorBoundary></MemoryRouter>);
  expect(screen.getByTestId("page-error").textContent).toContain("資料格式錯誤");
});
