# ExhibitIQ 開發進度

> 最後更新：2026-11-03｜負責人：專案負責人（`ai`）
> 工作項目編號見 [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)。
> **更新方式：** 本檔只由 `ai` 修改（同步到 `dev/data-platform` 時會覆蓋，對方修改會遺失）。資料工程的進度以 Albert 合併到 `dev/data-platform` 的 PR 為準，由 `ai` 讀取後更新本檔；只記錄已經在 GitHub 上查證的狀態。

## 目前階段

**Phase 1**（目標 D1–D4，11/03–11/06），進行中。

## 已完成

| 編號 | 項目 | PR | 合併到 | 合併日期 |
|---|---|---|---|---|
| A1-02、A1-03 | Repo 治理基礎：文件歸位、PR／Issue 模板、分支規則（舊編號 P1-AI-01） | [#2](https://github.com/magician-eric/exhibitiq/pull/2) | `dev/ai-intelligence` | 2026-11-03 |
| A1-04 | 模組邊界與 Schema 版本政策（舊編號 P1-AI-03） | [#4](https://github.com/magician-eric/exhibitiq/pull/4) | `dev/ai-intelligence` | 2026-11-03 |
| — | 第一次共用規範同步 | [#5](https://github.com/magician-eric/exhibitiq/pull/5) | `dev/data-platform` | 2026-11-03 |
| A1-05 | 核心資料契約 Schema v1（`1.0.0-draft.1`，舊編號 P1-AI-04） | [#8](https://github.com/magician-eric/exhibitiq/pull/8) | `dev/ai-intelligence` | 2026-11-03 |
| D1-01 | 雲端 Python 開發與執行環境設定（舊編號 P1-DATA-01） | [#9](https://github.com/magician-eric/exhibitiq/pull/9) | `dev/data-platform` | 2026-11-03 |
| — | 第二次共用規範同步：`schemas/v1/`、`docs/specs/`（來源 `dev/ai-intelligence` @ `127db55`；已查證兩邊一致） | [#10](https://github.com/magician-eric/exhibitiq/pull/10) | `dev/data-platform` | 2026-11-03 |
| D1-03 | 爬蟲／ETL 可重用目錄與程式骨架（舊編號 P1-DATA-02） | [#12](https://github.com/magician-eric/exhibitiq/pull/12) | `dev/data-platform` | 2026-11-03 |
| A1-08 | 簡化開發管理流程：開發計畫、進度檔、Web Dashboard 納入 MVP | [#13](https://github.com/magician-eric/exhibitiq/pull/13) | `dev/ai-intelligence` | 2026-11-03 |
| — | 第三次共用規範同步：V2.1 流程文件（已查證兩邊一致） | [#14](https://github.com/magician-eric/exhibitiq/pull/14) | `dev/data-platform` | 2026-11-03 |

`A1-02` 的兩條 dev 分支已建立（`dev/ai-intelligence`、`dev/data-platform`）。

## 進行中

| 編號 | 項目 | 狀態 |
|---|---|---|
| A1-06 | 分析結果與證據契約（Schema 升到 `1.0.0-draft.2`）；同時把合併人標記規則（Issue #15）寫進 `CLAUDE.md`、`branching.md`、PR 模板 | PR 待合併 |

## 待處理（Phase 1）

| 負責 | 編號 |
|---|---|
| ai | A1-01、A1-07、A1-09、W1-01、W1-02、W1-03 |
| data | D1-02、D1-04、D1-05、D1-06、D1-07、D1-08、D1-09、D1-10 |
| ai 準備、Albert 合併 | 第四次共用規範同步：A1-06 的 Schema、規格與合併人規則（A1-06 合併後） |
| data | A1-06 同步後，資料包 manifest 的 `schema_version` 改為 `1.0.0-draft.2`（草案期必須完全相同） |

## 阻礙事項

| 項目 | 影響 | 狀態 |
|---|---|---|
| MSPO 資料來源還沒確認能否取得 | Phase 2 真實資料展示；最大時程風險 | D1-10 |
| BXR 產品資料尚未提供 | A1-09 之後的 A2-05、W3-03 | 等專案負責人提供 |

## 待專案負責人決定

| 事項 | 需要在何時決定 |
|---|---|
| Phase 4 給評審的操作網址：公開的去敏感版 GitHub Pages（需確認帳號方案）、受保護的外部託管（新服務）、或只做現場操作 | Phase 3 結束前 |
| 根目錄 `.gitignore` 的負責人 | W1-01 開始前（前端會產生 `node_modules/`、`dist/`） |

## 已存在的 Issue（歷史紀錄）

Issue #15（合併人標記規則，跨人協調）是新制下的 Issue，等規則同步到 `dev/data-platform` 後關閉。

Issue #1、#3、#6、#7、#11 是取消強制 Issue 之前建立的，保留為歷史紀錄。#1、#3、#7 已關閉；#6、#11 屬於資料工程（對應的 PR #9、#12 已合併），由 Albert 自行處理。
