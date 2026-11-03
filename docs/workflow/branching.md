# ExhibitIQ 分支、PR 與階段整合規則

> 本文件整理自 [`docs/ExhibitIQ_專案總規範.md`](../ExhibitIQ_專案總規範.md) §2、§3、§9 與根目錄 [`CLAUDE.md`](../../CLAUDE.md)。兩者有衝突時，以總規範為準。

## 分支

| 分支 | 用途 | 建立來源 | PR base | 誰合併 |
|---|---|---|---|---|
| `main` | 只保存各階段驗收通過的整合版本 | — | — | 專案負責人 |
| `dev/ai-intelligence` | 專案負責人的長期開發主線 | `main` | — | 專案負責人 |
| `dev/data-platform` | 資料工程同事的長期開發主線 | `main` | — | 同事 |
| `feature/ai/<工作項目編號>-<slug>` | 專案負責人的單項任務 | `dev/ai-intelligence` | `dev/ai-intelligence` | 專案負責人 |
| `feature/data/<工作項目編號>-<slug>` | 同事的單項任務 | `dev/data-platform` | `dev/data-platform` | 同事 |
| `integration/phase-N` | 階段完成後的整合 | `main` | `main` | 專案負責人 |

## 單項工作流程

1. 從 [`DEVELOPMENT_PLAN.md`](../DEVELOPMENT_PLAN.md) 選定工作項目。一般工作**不需要建立 Issue**；Issue 只用於 Bug、重大需求變更、跨人協調或需要追蹤的問題（使用 `.github/ISSUE_TEMPLATE/task.md`）。
2. 從自己的 `dev/*` 建立 `feature/<role>/<工作項目編號小寫>-<slug>`，例如 `feature/ai/w1-01-frontend-scaffold`。
3. 只實作該工作項目的範圍，只修改自己負責的路徑；在雲端執行測試。
4. Push 並建立 PR（使用 `.github/pull_request_template.md`），標題格式為 `【<合併人> 合併】[<工作項目編號>] <摘要>`，base 設為自己的 `dev/*`。
5. 任務擁有者自行確認並合併。PR 存在不等於工作完成；測試未通過不得合併。
   **每個 PR 都要標明合併人**（Issue #15）：
   | PR base | 合併人 | 標題開頭 | 內文第一行 | Assignee |
   |---|---|---|---|---|
   | `dev/ai-intelligence`、`main` | Eric | `【Eric 合併】` | `> **合併人：Eric**` | `magician-eric` |
   | `dev/data-platform`（含同步 PR） | Albert | `【Albert 合併】` | `> ⚠️ **合併人：Albert。Eric 請勿合併。**` | `acyihung-infinityandbeyond` |
6. 前一項合併後，再從更新後的 `dev/*` 開始下一項（除非另有指示）。
7. 專案負責人依已合併的 PR 更新 [`PROGRESS.md`](../PROGRESS.md)；同事在 PR 描述中回報進度，不修改 `PROGRESS.md`。

## 階段整合

- 只有雙方在開發計畫中該階段的工作都完成、PR 都已合併到各自的 `dev/*` 之後才進行。
- 由專案負責人依 [`階段整合_ChatGPT指令模板.md`](階段整合_ChatGPT指令模板.md) 另行下達整合指令。
- 從 `main` 建立 `integration/phase-N`，整合兩條 dev 主線並執行端到端測試（含 Dashboard 與截圖），再建立 base=`main` 的 PR。
- 只有專案負責人驗收通過後才能合併 `main`；合併後，兩條 `dev/*` 以安全合併方式同步 `main`，不得丟棄未合併的工作。

## 共用規範同步

- 一般情況：`dev/ai-intelligence` → `dev/data-platform` 單向同步，Albert 合併（[`module-boundaries.md`](../architecture/module-boundaries.md) §4.3）。
- 專案負責人明確授權 Albert 修改共用文件時：先在 `dev/data-platform` 完成並由 Albert 合併，再以同步 PR 送到 `dev/ai-intelligence`，**只由 Eric 合併**（§4.6）。授權不改變模組所有權。

## 禁止事項

- 功能 PR 指向 `main`，或在階段進行中把 `dev/*` 合併進 `main`。
- 修改他人負責的開發主線或模組路徑。
- 未經專案負責人核准修改 `schemas/` 共用契約。
- GitHub Actions 自動寫入 `main`。
- 在核心程式（`etl/` 標準化與驗證、`schemas/`、`skills/` 分析邏輯、`site/` 頁面與元件）寫死特定展覽。

## 相關文件

- [開發計畫](../DEVELOPMENT_PLAN.md)與[進度](../PROGRESS.md)
- [模組邊界與目錄負責人](../architecture/module-boundaries.md)（含共用規範同步程序）
- [Schema 版本政策](../../schemas/VERSIONING.md)
- [ChatGPT 工作指令模板](ChatGPT_工作指令模板.md)
- [階段整合 ChatGPT 指令模板](階段整合_ChatGPT指令模板.md)
- [工作流程與驗收檢查表](工作流程與驗收檢查表.md)
