import { fireEvent, render, screen, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { ClaimBadge, CLAIM_STYLE, type ClaimKind } from "./components/status/ClaimBadge";
import { CompletenessIndicator } from "./components/status/CompletenessIndicator";
import { DataOriginBanner } from "./components/status/DataOriginBanner";
import { StatusBadge, type PipelineStatus } from "./components/status/StatusBadge";
import { t } from "./i18n/zh-TW";
import { NAV_ITEMS } from "./navigation";
import { antdTheme } from "./theme/tokens";

const wrap = (ui: React.ReactNode, path = "/") =>
  render(<ConfigProvider locale={zhTW} theme={antdTheme}><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></ConfigProvider>);

describe("navigation", () => {
  test("has exactly the 8 main menu items from the development plan", () => {
    expect(NAV_ITEMS.map((n) => n.label)).toEqual([
      "系統總覽", "展覽搜尋與新增", "展覽情報與比較", "參展商與企業情報",
      "商機分析與評分", "BXR 產品推薦", "AI 報告中心", "資料及系統狀態",
    ]);
    expect(new Set(NAV_ITEMS.map((n) => n.path)).size).toBe(8);
  });

  const BUILT = new Set(["overview", "companies"]);
  test.each(NAV_ITEMS.filter((n) => !BUILT.has(n.key)).map((n) => [n.path, n] as const))("route %s shows its title and the unified 建置中 state", (path, n) => {
    wrap(<App />, path);
    expect(screen.getAllByText(n.label).length).toBeGreaterThan(0);
    const uc = screen.getByTestId("under-construction");
    expect(within(uc).getByText(t.underConstruction.title)).toBeTruthy();
    expect(within(uc).getByText(t.underConstruction.body(n.plannedIn))).toBeTruthy();
  });

  test("clicking a menu item navigates", () => {
    wrap(<App />, "/");
    fireEvent.click(screen.getAllByText("資料及系統狀態")[0]);
    expect(screen.getByText(t.underConstruction.body("W2-05"))).toBeTruthy();
  });
});

describe("status components", () => {
  test("every ClaimBadge has its own text label (never colour only)", () => {
    const kinds = Object.keys(CLAIM_STYLE) as ClaimKind[];
    wrap(<>{kinds.map((k) => <ClaimBadge key={k} kind={k} />)}</>);
    for (const k of kinds) expect(screen.getByText(t.claim[k])).toBeTruthy();
    expect(new Set(kinds.map((k) => t.claim[k])).size).toBe(kinds.length);
  });

  test("AI inference never looks like verified fact", () => {
    expect(CLAIM_STYLE.ai_inferred.color).not.toBe(CLAIM_STYLE.verified.color);
    expect(t.claim.ai_inferred).not.toBe(t.claim.verified);
  });

  test("every StatusBadge renders a label", () => {
    const all = Object.keys(t.status) as PipelineStatus[];
    wrap(<>{all.map((s) => <StatusBadge key={s} status={s} />)}</>);
    for (const s of all) expect(screen.getByText(t.status[s])).toBeTruthy();
  });

  test("missing official count is shown as 未知, never a number", () => {
    wrap(<CompletenessIndicator status="unknown" official={null} collected={5} />);
    expect(screen.getByText(/已取得 5 ／ 官方公布 未知/)).toBeTruthy();
  });

  test("synthetic data shows the banner; collected data does not", () => {
    const { unmount } = wrap(<DataOriginBanner origin="synthetic" />);
    expect(screen.getByTestId("data-origin-banner")).toBeTruthy();
    unmount();
    wrap(<DataOriginBanner origin="collected" />);
    expect(screen.queryByTestId("data-origin-banner")).toBeNull();
  });
});

describe("source rules", () => {
  const files: string[] = [];
  const walk = (d: string) => readdirSync(d).forEach((f) => {
    const p = join(d, f);
    if (statSync(p).isDirectory()) walk(p); else if (/\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f)) files.push(p);
  });
  walk("src");

  test("colours are defined only in theme/tokens.ts", () => {
    for (const f of files.filter((f) => !f.endsWith(join("theme", "tokens.ts")))) {
      expect(readFileSync(f, "utf8"), f).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(/);
    }
  });

  test("no specific exhibition is hard-coded in the Dashboard (V2.3)", () => {
    for (const f of files) expect(readFileSync(f, "utf8"), f).not.toMatch(/MSPO|TADTE/i);
  });
});
