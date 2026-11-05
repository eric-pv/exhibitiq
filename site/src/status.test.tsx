import { render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { bundle, getSystemStatus } from "./data/repository";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

test("status numbers come from the dataset index, failures included", () => {
  const v = getSystemStatus();
  const editions = bundle.exhibitions.flatMap((e) => e.editions);
  expect(v.editions.length).toBe(editions.length);
  expect(v.datasets.length).toBe(editions.reduce((n, e) => n + e.datasets.length, 0));
  expect(Object.values(v.acquisition).reduce((a, b) => a + b, 0)).toBe(editions.length);
  expect(v.acquisition.failed).toBeGreaterThan(0); // the example index records a failed acquisition
  expect(v.notices.length).toBe(bundle.notices.length);
});

test("status page shows acquisition, validation and notices", () => {
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/status"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getByTestId("failed-note")).toBeTruthy();
  expect(within(screen.getByTestId("status-acquisition")).getAllByText("失敗").length).toBeGreaterThan(0);
  expect(within(screen.getByTestId("status-validation")).getAllByText("驗證通過").length).toBeGreaterThan(0);
  expect(within(screen.getByTestId("status-notices")).getAllByRole("alert").length).toBe(bundle.notices.length);
});
