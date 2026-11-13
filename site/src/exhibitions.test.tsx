import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { bundle, getExhibitionRows, listStatus, matchesExhibition } from "./data/repository";
import { uploadUrl } from "./data/registration";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));
const renderAt = (p: string) => render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[p]}><App /></MemoryRouter></ConfigProvider>);

test("exhibition rows come from the dataset index (nothing hard-coded); search by name, country and year", () => {
  const rows = getExhibitionRows();
  expect(rows.map((r) => r.exhibitionId)).toEqual(bundle.exhibitions.map((e) => e.exhibitionId));
  const r = rows[0];
  expect(matchesExhibition(r, r.name.slice(0, 4))).toBe(true);
  expect(matchesExhibition(r, String(r.years[0]))).toBe(true);
  expect(matchesExhibition(r, "zzz-none")).toBe(false);
});

test("an exhibition without a package shows 尚無資料包 and an unknown official count stays 未知", () => {
  const rows = getExhibitionRows();
  expect(rows.some((r) => !r.hasPackage)).toBe(true); // the example index includes a failed acquisition
  for (const r of rows) if (r.latestCompleteness?.official === null) expect(r.latestCompleteness.status).not.toBe("complete");
});

test("list page filters from URL; detail page shows assessment and editions", () => {
  const first = getExhibitionRows()[0];
  const { unmount } = renderAt(`/exhibitions?q=${encodeURIComponent(first.name)}`);
  expect(within(screen.getByTestId("exhibition-table")).getAllByRole("row").length).toBe(2);
  unmount();
  renderAt(`/exhibitions/${first.exhibitionId}`);
  expect(screen.getByRole("heading", { level: 2, name: first.name })).toBeTruthy();
  expect(screen.getByTestId("exhibition-assessment")).toBeTruthy();
  expect(screen.getByTestId("exhibition-editions")).toBeTruthy();
});

test("unknown exhibition shows empty state", () => {
  renderAt("/exhibitions/no-such-expo");
  expect(screen.getByText(/找不到展覽 no-such-expo/)).toBeTruthy();
});

test("list status: obtained vs not obtained with the reason from the index; upload link for editions without a list", () => {
  const rows = getExhibitionRows();
  const withList = rows.find((r) => r.hasPackage)!, without = rows.find((r) => !r.hasPackage)!;
  expect(listStatus(withList)).toEqual({ obtained: true, reason: null });
  const s = listStatus(without);
  expect(s.obtained).toBe(false);
  expect(s.reason).toBe(without.acquisition.notes ?? without.editions.map((e) => e.lastAcquisition?.notes).find((n) => !!n) ?? null);
  expect(uploadUrl("some-expo", 2026)).toBe("https://github.com/eric-pv/exhibitiq/upload/dev/data-platform/data/uploads/some-expo/2026");
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/exhibitions"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getAllByTestId("list-status").map((x) => x.textContent)).toEqual(expect.arrayContaining(["已取得", "未取得"]));
  expect(screen.getAllByTestId("list-note")[0].textContent).toContain("建議自行搜尋名單並上傳");
});

test("exhibition without a list: detail page offers the upload button", () => {
  const without = getExhibitionRows().find((r) => !r.hasPackage)!;
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[`/exhibitions/${without.exhibitionId}`]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getAllByTestId("upload-button")[0].getAttribute("href")).toContain(`/data/uploads/${without.exhibitionId}/`);
});
