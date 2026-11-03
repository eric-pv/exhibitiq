# ExhibitIQ

AI-powered exhibition intelligence and strategic analysis platform（Big x Reality 內部 AI 應用實戰挑戰賽 — 競賽版）。

ExhibitIQ 以爬蟲與 ETL 蒐集展會參展商公開資料，經清理與標準化後打包成資料包，再由 Claude Code ExhibitIQ Skill 分析，產出有來源、可追溯的展會與市場情報；所有資料、分析結果與系統狀態都在 **Web Dashboard** 上搜尋、篩選、比較並匯出報告。

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
| [`docs/workflow/ChatGPT_工作指令模板.md`](docs/workflow/ChatGPT_工作指令模板.md) | 單一工作項目的 ChatGPT 指令模板 |
| [`docs/workflow/階段整合_ChatGPT指令模板.md`](docs/workflow/階段整合_ChatGPT指令模板.md) | 階段整合指令模板（僅專案負責人） |
| [`docs/workflow/工作流程與驗收檢查表.md`](docs/workflow/工作流程與驗收檢查表.md) | PR、階段與安全檢查表 |

## 分支概要

- `main`：只保存階段驗收通過的整合版本。
- `dev/ai-intelligence`：AI Skill、分析、產品知識、報告與 Web Dashboard（專案負責人）。
- `dev/data-platform`：爬蟲、ETL、資料品質與 GitHub Actions（資料工程）。
- 每個工作項目一條 `feature/<ai|data>/<工作項目編號>-<slug>`，PR base 指向自己的 `dev/*`；一般工作不需要 Issue。

## 目前狀態

Phase 1（架構與雲端開發基礎）進行中。詳細進度見 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
