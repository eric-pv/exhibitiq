import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { getCompanyRows, matchesQuery, toCsv } from "./data/repository";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

test("company rows come from the bundle and search covers aliases", () => {
  const rows = getCompanyRows();
  expect(rows.length).toBeGreaterThan(0);
  const withAlias = rows.find((r) => r.aliases.length > 0)!;
  expect(matchesQuery(withAlias, withAlias.aliases[0].slice(0, 6))).toBe(true);
  expect(matchesQuery(withAlias, "zzz-no-such-company")).toBe(false);
});

test("CSV has a UTF-8 BOM and escapes commas", () => {
  const csv = toCsv(["a", "b"], [["x,y", null]]);
  expect(csv.charCodeAt(0)).toBe(0xfeff);
  expect(csv).toContain('"x,y",');
});

test("companies page renders table, filters from URL; verification shown as a compact icon (no booth / listing columns)", () => {
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/companies?q=placeholder"]}><App /></MemoryRouter></ConfigProvider>);
  const table = screen.getByTestId("company-table");
  expect(within(table).getAllByRole("row").length).toBe(2); // header + 1 filtered row
  expect(within(table).queryByText("未公布")).toBeNull();
  expect(within(table).getAllByTestId("claim-icon")[0].getAttribute("aria-label")).toBeTruthy();
  expect(screen.getByTestId("csv-export")).toBeTruthy();
});

test("W3-05: CSV is Excel-safe — CRLF rows, quoted newlines/quotes, formula cells neutralised, numbers kept", () => {
  const csv = toCsv(["a", "b", "c"], [["=HYPERLINK(\"x\")", -5, "line1\nline2"], ["@cmd", "+1", "正常"]]);
  const lines = csv.slice(1).split("\r\n");
  expect(lines[0]).toBe("a,b,c");
  expect(lines[1]).toBe(`"'=HYPERLINK(""x"")",-5,"line1\nline2"`);
  expect(lines[2]).toBe("'@cmd,'+1,正常");
  expect(csv.endsWith("\r\n")).toBe(true);
});
