# ExhibitIQ 分支、PR 與階段整合規則

> 本文件整理自 [`docs/ExhibitIQ_專案總規範.md`](../ExhibitIQ_專案總規範.md) §2、§3、§9 與根目錄 [`CLAUDE.md`](../../CLAUDE.md)。兩者有衝突時，以總規範為準。

## 分支

| 分支 | 用途 | 建立來源 | PR base | 誰合併 |
|---|---|---|---|---|
| `main` | 只保存各階段驗收通過的整合版本 | — | — | 專案負責人 |
| `dev/ai-intelligence` | 專案負責人的長期開發主線 | `main` | — | 專案負責人 |
| `dev/data-platform` | 資料工程同事的長期開發主線 | `main` | — | 同事 |
| `feature/ai/<issue>-<slug>` | 專案負責人的單項任務 | `dev/ai-intelligence` | `dev/ai-intelligence` | 專案負責人 |
| `feature/data/<issue>-<slug>` | 同事的單項任務 | `dev/data-platform` | `dev/data-platform` | 同事 |
| `integration/phase-N` | 階段完成後的整合 | `main` | `main` | 專案負責人 |

## 單項工作流程

1. 建立 Issue（使用 `.github/ISSUE_TEMPLATE/task.md`），指定 Phase、唯一負責人、允許／禁止路徑、依賴、Schema、測試與驗收條件。
2. 從自己的 `dev/*` 建立 `feature/<role>/<issue>-<slug>`。
3. 只實作該 Issue 的範圍；在雲端執行測試。
4. Push 並建立 PR（使用 `.github/pull_request_template.md`），base 設為自己的 `dev/*`。
5. 任務擁有者自行確認並合併。PR 存在不等於工作完成；測試未通過不得合併。
6. 前一項合併後，再從更新後的 `dev/*` 開始下一項（除非另有指示）。

## 階段整合

- 只有雙方該階段的 Issue 全部完成、PR 都已合併到各自的 `dev/*` 之後才進行。
- 由專案負責人依 [`階段整合_ChatGPT指令模板.md`](階段整合_ChatGPT指令模板.md) 另行下達整合指令。
- 從 `main` 建立 `integration/phase-N`，整合兩條 dev 主線並執行端到端測試，再建立 base=`main` 的 PR。
- 只有專案負責人驗收通過後才能合併 `main`；合併後，兩條 `dev/*` 以安全合併方式同步 `main`，不得丟棄未合併的工作。

## 禁止事項

- 功能 PR 指向 `main`，或在階段進行中把 `dev/*` 合併進 `main`。
- 修改他人負責的開發主線或模組路徑。
- 未經專案負責人核准修改 `schemas/` 共用契約。
- GitHub Actions 自動寫入 `main`。

## 相關文件

- [ChatGPT 工作指令模板](ChatGPT_工作指令模板.md)
- [階段整合 ChatGPT 指令模板](階段整合_ChatGPT指令模板.md)
- [工作流程與驗收檢查表](工作流程與驗收檢查表.md)
