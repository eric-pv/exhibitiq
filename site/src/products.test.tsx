import { render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { bundle, getProducts } from "./data/repository";
import type { Bundle } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));

test("only approved product cards are shown", () => {
  expect(getProducts().length).toBe(bundle.settings.products.filter((p) => p.approvalStatus === "approved").length);
  const draftOnly = { ...bundle, settings: { ...bundle.settings, products: bundle.settings.products.map((p) => ({ ...p, approvalStatus: "draft" })) } } as Bundle;
  expect(getProducts(draftOnly)).toEqual([]);
});

test("products page renders the approved cards", () => {
  render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={["/products"]}><App /></MemoryRouter></ConfigProvider>);
  expect(screen.getAllByTestId("product-card").length).toBe(getProducts().length);
  expect(screen.getByText("兵棋圖台")).toBeTruthy();
});
