# ExhibitIQ

AI-powered exhibition intelligence and strategic analysis platform（Big x Reality 內部 AI 應用實戰挑戰賽 — 競賽版）。

ExhibitIQ 以爬蟲與 ETL 蒐集展會參展商公開資料，經清理與標準化後打包成資料包，再由 Claude Code ExhibitIQ Skill 分析，產出有來源、可追溯的展會與市場情報報告。

## 從這裡開始

| 文件 | 說明 |
|---|---|
| [`docs/ExhibitIQ_專案總規範.md`](docs/ExhibitIQ_專案總規範.md) | 最高層規格：架構、分工、資料契約、四階段規劃 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 工作規則 |
| [`docs/workflow/branching.md`](docs/workflow/branching.md) | 分支、PR 與階段整合規則 |
| [`docs/workflow/ChatGPT_工作指令模板.md`](docs/workflow/ChatGPT_工作指令模板.md) | 單一 Issue 的 ChatGPT 指令模板 |
| [`docs/workflow/階段整合_ChatGPT指令模板.md`](docs/workflow/階段整合_ChatGPT指令模板.md) | 階段整合指令模板（僅專案負責人） |
| [`docs/workflow/工作流程與驗收檢查表.md`](docs/workflow/工作流程與驗收檢查表.md) | PR、階段與安全檢查表 |

## 分支概要

- `main`：只保存階段驗收通過的整合版本。
- `dev/ai-intelligence`：AI Skill、分析、產品知識與報告（專案負責人）。
- `dev/data-platform`：爬蟲、ETL、資料品質與 GitHub Actions（資料工程）。
- 每個 Issue 一條 `feature/<ai|data>/<issue>-<slug>`，PR base 指向自己的 `dev/*`。

## 目前狀態

Phase 1（架構與雲端開發基礎）進行中。程式模組、`schemas/` 與 Skill 尚未建立。
