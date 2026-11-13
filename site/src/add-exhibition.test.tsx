import { fireEvent, render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { loadValidators } from "../scripts/build-bundle.mjs";
import App from "./App";
import { bundle } from "./data/repository";
import { ADD_EXHIBITION_WORKFLOW, buildRegistration, possibleDuplicates, proposeId, validateRegistration, workflowInputs, workflowUrl } from "./data/registration";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));
const NOW = new Date("2026-11-09T01:02:03.456Z");

test("proposed id: English name, then name, then website host; suffix when taken; null when nothing usable", () => {
  expect(proposeId({ name: "台北國際航太暨國防工業展", nameEn: "Taipei Aerospace & Defense Expo 2026" }, [])).toBe("taipei-aerospace-defense-expo-2026");
  expect(proposeId({ name: "某某展", website: "https://www.some-fair.example/zh" }, [])).toBe("some-fair");
  expect(proposeId({ name: "Example Expo" }, ["example-expo", "example-expo-2"])).toBe("example-expo-3");
  expect(proposeId({ name: "2026 展" }, [])).toBeNull();
});

test("registration follows A1-10: valid in the browser AND with the build-time validator; requested via dashboard_form", () => {
  const doc = buildRegistration({ name: " New Fair ", country: "tw", website: "https://new.example/", years: [2027, 2026, 2026], requestedBy: "Eric", exhibitionId: "new-fair" }, NOW);
  expect(doc).toMatchObject({ schema_version: bundle.schemaVersion, name: "New Fair", country: "TW", years: [2026, 2027],
    registration_status: "requested", request_channel: "dashboard_form", requested_at: "2026-11-09T01:02:03Z" });
  expect(validateRegistration(doc)).toEqual([]);
  expect(() => loadValidators().check("exhibition_registration", doc, "form")).not.toThrow();
  expect(workflowInputs(doc)).toContainEqual(["years", "2026,2027"]);
});

test("invalid input is reported, never silently fixed", () => {
  expect(validateRegistration(buildRegistration({ name: "X", years: [], requestedBy: "Eric", exhibitionId: "x" }, NOW)).length).toBeGreaterThan(0);
  expect(validateRegistration(buildRegistration({ name: "X", years: [2026], requestedBy: "Eric", exhibitionId: "x", website: "ftp://x" }, NOW)).length).toBeGreaterThan(0);
  expect(validateRegistration(buildRegistration({ name: "X", years: [2026], requestedBy: "Eric", exhibitionId: "Bad_ID" }, NOW)).length).toBeGreaterThan(0);
});

test("possible duplicates: same id, same name or same website host as a registered exhibition", () => {
  const ex = bundle.exhibitions.find((e) => e.website)!;
  expect(possibleDuplicates({ name: "Other", years: [2026], requestedBy: "x", website: ex.website! }).map((d) => d.exhibitionId)).toContain(ex.exhibitionId);
  expect(possibleDuplicates({ name: ex.name, years: [2026], requestedBy: "x" }).map((d) => d.exhibitionId)).toContain(ex.exhibitionId);
  expect(possibleDuplicates({ name: "Totally New", years: [2026], requestedBy: "x", website: "https://new.example" })).toEqual([]);
});

test("workflow link only once D2-13 exists (Actions page of this repo)", () => {
  expect(ADD_EXHIBITION_WORKFLOW).toBeNull();
  expect(workflowUrl()).toBeNull();
  expect(workflowUrl("add-exhibition.yml")).toBe("https://github.com/eric-pv/exhibitiq/actions/workflows/add-exhibition.yml");
});

test("form: fills in, shows the JSON and 'workflow not yet available'; sends nothing", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/exhibitions?add=1"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getByTestId("add-invalid")).toBeTruthy(); // empty form is not a valid registration
  fireEvent.change(screen.getByTestId("add-name").querySelector("input") ?? screen.getByTestId("add-name"), { target: { value: "New Fair" } });
  fireEvent.change(screen.getByTestId("add-requested-by").querySelector("input") ?? screen.getByTestId("add-requested-by"), { target: { value: "Eric" } });
  expect(screen.getByTestId("add-json").textContent).toContain('"exhibition_id": "new-fair"');
  expect(screen.getByTestId("add-no-workflow")).toBeTruthy();
  expect(fetchSpy).not.toHaveBeenCalled();
});
