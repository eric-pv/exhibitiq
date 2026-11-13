# ExhibitIQ

AI-powered exhibition intelligence and strategic analysis platform（Big x Reality 內部 AI 應用實戰挑戰賽 — 競賽版）。

ExhibitIQ 是**可支援不同展覽的通用型** AI 展會情報搜尋、蒐集、分析與可視化平台：使用者搜尋或新增展覽（名稱、國家、年份或官網），經來源評估後擷取或匯入參展商資料，以共用 Schema 標準化並打包成資料包，再由 Claude Code ExhibitIQ Skill 進行企業情報、商機、競品、合作及產品適配分析；結果在 **Web Dashboard** 上搜尋、篩選、跨展覽與跨年度比較，並匯出 PDF／CSV 報告。

系統不以任何特定展覽為開發目標、預設來源或必要驗收對象，展覽與資料來源一律經通用的來源探索與評估流程決定；並非每個展覽都能自動取得完整資料，系統保留來源適配、檔案匯入、部分成功與資料不足的處理（見總規範 §1.1、§4.1）。

## 三個核心模組

| 模組 | 負責人 | 主要路徑 |
|---|---|---|
| Data Platform | data（Albert） | `crawler/`、`etl/`、`data/`、`.github/workflows/`、`tests/data/` |
| AI Intelligence | ai（Eric） | `schemas/`、`skills/`、`knowledge/`、`reports/`、`tests/contract/` |
| Web Dashboard | ai（Eric） | `site/` |

## 從這裡開始

| 文件 | 說明 |
|---|---|
| [`docs/ExhibitIQ_專案總規範.md`](docs/ExhibitIQ_專案總規範.md) | 最高層規格：架構、分工、資料契約、四階段關卡 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 工作規則 |
| [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) | 四階段開發計畫：工作項目、分工、依賴、驗收、可視化成果 |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | 目前進度、PR 連結、待處理工作與阻礙 |
| [`docs/workflow/branching.md`](docs/workflow/branching.md) | 分支、PR 與階段整合規則 |
| [`docs/architecture/module-boundaries.md`](docs/architecture/module-boundaries.md) | 目錄負責人、跨範圍修改、共用規範同步 |
| [`schemas/VERSIONING.md`](schemas/VERSIONING.md) | Schema 版本、相容性與變更程序 |
| [`docs/specs/data-package-contract.md`](docs/specs/data-package-contract.md) | 資料包契約 v1：ID、目錄、序列化、雜湊、來源追溯、完整度 |
| [`docs/specs/analysis-result-contract.md`](docs/specs/analysis-result-contract.md) | 分析結果契約 v1：結論類型、不確定性、可拆解評分、關係分類、建議 |
| [`docs/specs/dataset-index-contract.md`](docs/specs/dataset-index-contract.md) | 資料集索引契約 v1：已登錄展覽、取得方式與評估、取得結果、資料包與驗證狀態 |
| [`docs/specs/mvp-scope.md`](docs/specs/mvp-scope.md) | 競賽 MVP 範圍（M／A／F 分級）與 14 項能力驗收指標 |
| [`docs/specs/exhibition-registry-contract.md`](docs/specs/exhibition-registry-contract.md) | 展覽登錄契約 v1：展覽名冊 `data/registry/<exhibition_id>/registration.json` |
| [`docs/specs/knowledge-base-contract.md`](docs/specs/knowledge-base-contract.md) | 知識庫契約 v1：BXR 產品卡（依據文件、核定狀態）與六個分析分類面向 |
| [`docs/workflow/ChatGPT_工作指令模板.md`](docs/workflow/ChatGPT_工作指令模板.md) | 單一工作項目的 ChatGPT 指令模板 |
| [`docs/workflow/階段整合_ChatGPT指令模板.md`](docs/workflow/階段整合_ChatGPT指令模板.md) | 階段整合指令模板（僅專案負責人） |
| [`docs/workflow/工作流程與驗收檢查表.md`](docs/workflow/工作流程與驗收檢查表.md) | PR、階段與安全檢查表 |

## 分支概要

- `main`：只保存階段驗收通過的整合版本。
- `dev/ai-intelligence`：AI Skill、分析、產品知識、報告與 Web Dashboard（專案負責人）。
- `dev/data-platform`：爬蟲、來源評估與匯入、ETL、資料品質與 GitHub Actions（資料工程）。
- 每個工作項目一條 `feature/<ai|data>/<工作項目編號>-<slug>`，PR base 指向自己的 `dev/*`；一般工作不需要 Issue。

## 目前狀態

Phase 1（架構與雲端開發基礎）進行中。詳細進度見 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
