# site/ — ExhibitIQ Web Dashboard

- **負責人：** Eric（`ai`）。建置、預覽與發布的 workflow 在 `.github/workflows/`，由 Albert（`data`）負責。
- **架構與規則：** [`docs/DEVELOPMENT_PLAN.md`](../docs/DEVELOPMENT_PLAN.md) §3（Web Dashboard 架構）。
- **目前狀態：** W1-01 前端骨架。設計系統、主選單（W1-02）與資料存取層（W1-03）尚未加入。

## 技術

React 18、Vite 6、TypeScript 5、Ant Design 5（`zh_TW` 語系）、ECharts 5、React Router（HashRouter）、Vitest、Playwright。版本鎖定在 `package.json` 與 `package-lock.json`。

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
