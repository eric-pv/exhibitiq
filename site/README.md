# site/ — ExhibitIQ Web Dashboard

- **負責人：** Eric（`ai`）。建置、預覽與發布的 workflow 在 `.github/workflows/`，由 Albert（`data`）負責。
- **架構與規則：** [`docs/DEVELOPMENT_PLAN.md`](../docs/DEVELOPMENT_PLAN.md) §3（Web Dashboard 架構）。
- **目前狀態：** Phase 1 完成（W1-01～W1-03）：設計系統、8 個主選單、資料存取層，以及用合成資料顯示的系統總覽。其他 7 個頁面顯示「建置中」。

## 結構

| 路徑 | 內容 |
|---|---|
| `src/theme/tokens.ts` | **唯一**的設計 token（色彩、間距、字級、圓角、版面）與 Ant Design 主題；其他檔案不得寫色碼（測試強制） |
| `src/i18n/zh-TW.ts` | 所有介面文字（繁體中文優先，預留英文） |
| `src/navigation.tsx` | 8 個主選單；不寫死任何展覽（測試強制） |
| `src/components/layout/` | `AppLayout`（側邊選單，手機版收合並覆蓋在內容上方）、`PageHeader` |
| `src/components/status/` | `ClaimBadge`（查證狀態與 AI 推論）、`StatusBadge`（取得、驗證、來源評估）、`CompletenessIndicator`（官方筆數缺少時顯示「未知」）、`DataOriginBanner`（合成資料橫幅） |
| `src/components/states/` | `LoadingState`、`EmptyState`、`ErrorState`、`UnderConstruction`（建置中） |
| `src/pages/DesignSystemPage.tsx` | 元件參考頁 `#/design`（不在主選單） |
| `src/components/KpiCard.tsx`、`ChartPanel.tsx` | 統計卡片（可點擊進入）、長條圖面板（統一配色、空狀態、來源說明、隨容器調整寬度） |
| `scripts/build-bundle.mjs` | **bundle 產生程式**：讀取資料集索引 → 最新資料包 → 分析結果，**每份輸入先用 `schemas/v1/` 驗證**，不合格就停止；輸出 `src/generated/bundle.json`（不進 Git） |
| `src/data/` | `repository.ts`（頁面唯一的資料入口）、`types.ts`（bundle 的 view model） |
| `src/pages/OverviewPage.tsx` | 系統總覽：4 張統計卡片、2 張圖表、展覽資料狀態、最近一次 AI 分析、系統通知、資料來源 |

## 資料來源

`npm run bundle`（`build`、`test`、`typecheck` 前會自動執行）：

- 資料集索引：`data/index/datasets.json`（Albert 的 D2-12 產生後），在那之前使用 `schemas/v1/examples/index/dataset_index.example.json`。
- 分析結果：`reports/analysis/`，在那之前使用 `schemas/v1/examples/analysis/`。
- 可以用 `BUNDLE_INDEX`、`BUNDLE_ANALYSES` 環境變數指定其他檔案。
- 範例資料都是合成資料，頁面會顯示合成資料橫幅。

狀態一律用「顏色＋圖示＋文字」表示，不只靠顏色；AI 推論的顏色和「已查證」不同。

## 技術

React 18、Vite 6、TypeScript 5、Ant Design 5（`zh_TW` 語系）、ECharts 5（直接使用，由 `ChartPanel` 管理尺寸）、React Router（HashRouter）、Vitest、Playwright；bundle 產生程式使用 Ajv 8（JSON Schema Draft 2020-12）。版本鎖定在 `package.json` 與 `package-lock.json`。

## 指令（在 `site/` 目錄執行）

| 指令 | 用途 |
|---|---|
| `npm ci` | 依 lockfile 安裝套件 |
| `npm run dev` | 開發伺服器 |
| `npm run typecheck` | TypeScript 型別檢查 |
| `npm test` | 單元測試（Vitest） |
| `npm run build` | 一般打包，輸出 `dist/` |
| `npm run build:single` | 打包成**單一 HTML 檔**，輸出 `dist-single/index.html`，可直接從磁碟開啟，用於私有預覽 artifact |
| `npm run test:e2e` | 端到端測試（Playwright）；需要先執行 `build` 和 `build:single`。設定 `SCREENSHOT_DIR` 環境變數時會輸出桌機與手機截圖 |

**Playwright 瀏覽器：** 雲端工作區已預先安裝（`PLAYWRIGHT_BROWSERS_PATH`）；GitHub Actions 中要先執行 `npx playwright install --with-deps chromium`。`@playwright/test` 版本固定為 1.63.0。

## 規則摘要

- 頁面只透過 `src/data/` 讀取有 Schema 的資料，不直接讀取爬蟲輸出（W1-03 起）。
- 不寫死任何展覽；展覽清單只來自資料集索引。
- 前端不放任何 Token 或 API Key。
- 打包產物（`dist/`、`dist-single/`）、`node_modules/`、測試輸出不進 Git（見根目錄 `.gitignore`）。

## 錯誤處理（W4-03）

| 情況 | 行為 |
|---|---|
| 資料驗證失敗（Schema、雜湊、引用的來源不存在） | `npm run bundle` 停止並列出檔案與原因；不會產生含錯誤資料的網站（`scripts/build-bundle.mjs`） |
| 頁面載入或顯示時發生錯誤 | 該頁顯示統一的錯誤狀態（`ErrorBoundary` → `ErrorState`），切換到其他頁面即恢復 |
| 沒有資料（沒有展覽、資料包或分析結果） | 各頁顯示統一的空狀態或「資料不足」，數字為 0 或「未知」，不推測補足 |
| 個別屆次取得失敗 | 系統狀態頁與總覽列出失敗與原因，不隱藏 |

## 安全檢查（W4-05）

`npm run build && npm run build:single && npm run security`：掃描 `dist/`、`dist-single/` 與 `src/`，發現任何 Token、API Key、私鑰、Bearer 憑證，或呼叫 GitHub API／LLM API 的程式就失敗。規則本身由 `src/security.test.ts` 測試。
公開版（GitHub Pages）的內容白名單要等專案負責人決定發布方式後再加入（開發計畫「待專案負責人決定」）。
