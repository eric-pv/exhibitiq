import { render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

// jsdom has no layout engine; ECharts is exercised in the Playwright test.
vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echarts-stub" /> }));

beforeAll(() => {
  // Ant Design reads matchMedia for responsive behaviour.
  window.matchMedia = window.matchMedia || ((q: string) => ({
    matches: false, media: q, onchange: null, addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false,
  }) as unknown as MediaQueryList);
});

test("scaffold page renders title, scaffold notice and chart card", () => {
  render(
    <ConfigProvider locale={zhTW}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </ConfigProvider>,
  );
  expect(screen.getByRole("heading", { name: "ExhibitIQ Dashboard" })).toBeTruthy();
  expect(screen.getByText("前端骨架（W1-01）")).toBeTruthy();
  expect(screen.getByText("圖表元件驗證（不是資料）")).toBeTruthy();
  expect(screen.getByTestId("echarts-stub")).toBeTruthy();
});
