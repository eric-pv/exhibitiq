import { render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { bundle } from "./data/repository";
import { analysisInstruction, estimateInputTokens } from "./pages/RunAnalysis";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

test("instruction: prepare → fill only the judgement → finalize → PR; never asks for money or a key", () => {
  const s = analysisInstruction("some-expo", 2026, "bxr-opportunity");
  expect(s).toContain("exhibitiq_tools.py prepare some-expo 2026 --profile bxr-opportunity");
  expect(s).toContain("exhibitiq_tools.py finalize");
  expect(s).toContain("scores 保持不變");
  expect(s).not.toMatch(/API[_ ]?KEY|token=/i);
});

test("estimate grows slowly past the detail limit (top N in detail, the rest one line each)", () => {
  expect(estimateInputTokens(2)).toBeLessThan(estimateInputTokens(40));
  expect(estimateInputTokens(800) - estimateInputTokens(40)).toBeLessThan(estimateInputTokens(40));
});

test("exhibition detail: run-analysis card for an exhibition with a package; explains when there is none", () => {
  const withPkg = bundle.exhibitions.find((e) => e.editions.some((ed) => ed.latestDatasetId))!;
  const { unmount } = render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[`/exhibitions/${withPkg.exhibitionId}`]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getByTestId("run-instruction").textContent).toContain(`prepare ${withPkg.exhibitionId}`);
  expect(screen.getByTestId("run-estimate").textContent).toContain("token");
  unmount();
  const none = bundle.exhibitions.find((e) => e.editions.every((ed) => !ed.latestDatasetId));
  if (none) {
    render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[`/exhibitions/${none.exhibitionId}`]}><App /></MemoryRouter></ConfigProvider>);
    expect(screen.getByTestId("run-analysis").textContent).toContain("還沒有驗證通過的資料包");
  }
});
