# 在 GitHub Actions 執行資料工作（data-run）

> 工作項目：D2-05（Actions 執行；2026-11-12 Albert 同意恢復：「在 GitHub Actions 上執行爬蟲」）｜負責人：data
> 程式：`.github/workflows/data-run.yml`、`etl/data_run.py`｜測試：`tests/data/test_data_run.py`｜本文件只記錄已實作並測試過的行為。

## 1. 為什麼

雲端工作環境沒有本機 DNS（網址由代理解析），而爬蟲的安全檢查必須先在本機解析網址、確認不是內部網路，所以爬蟲在工作環境中無法連線（這項檢查不放寬）。GitHub Actions 的執行環境有正常 DNS，爬蟲與所有安全規則照常運作。

## 2. 怎麼用

1. 從 `dev/data-platform` 建立分支 `data-run/<說明>`，加入 `data-run/request.json`：

   ```json
   {"steps": [
     {"command": "enrich", "package": "data/packages/iacp/2026/iacp-2026.20261109T071220Z", "targets": "data/sources/iacp/iacp-2026.enrich.json", "notes": "..."},
     {"command": "build_index"}
   ]}
   ```

2. 推送分支 → workflow 自動執行 → 結果（`data/` 的新檔案、`data-run/report.json`）以 `[data-run result]` commit 推回同一分支。
3. 檢查結果（驗證、測試），把 `data/` 的結果放進 `feature/data/*` 分支，PR 到 `dev/data-platform`。`data-run/` 目錄不進 `dev/data-platform`。

## 3. 允許的指令（白名單）

| command | 參數 | 執行 |
|---|---|---|
| `enrich` | `package`、`targets`、`notes` | `python -m etl.enrich` |
| `import_file` | `config`、`file`、`info`、`country_aliases`、`official_count`、`official_as_of`、`notes`、`accept` | `python -m etl.import_file` |
| `build_index` | — | `python -m etl.build_index` |
| `validate` | `package` | `python -m etl.validate` |

- 其他指令、未知參數、`data/` 以外的路徑（含 `..`、絕對路徑）→ 整個請求拒絕，**一步都不執行**。最多 20 步。
- 依序執行，第一個失敗的步驟停止；報告記錄每步的模組、參數、結束碼與輸出。
- 即使請求失敗，已產生的證據（例如失敗的擷取紀錄）仍會推回分支，方便檢查。

## 4. 安全設計

| 項目 | 做法 |
|---|---|
| 觸發 | 只有推送到 `data-run/**` 分支（只有有寫入權限的人能推）；沒有 `pull_request_target`、`workflow_run` |
| 權限 | `contents: write`（只用來推回觸發的分支）；不使用任何 secrets |
| 寫入範圍 | 推送前檢查分支名稱必須是 `data-run/*`；**不寫 `main` 或任何 `dev/*`** |
| 不循環 | GitHub 內建 token 的推送不會觸發 workflow；另檢查 commit 訊息 `[data-run result]` |
| 同時執行 | 同一分支排隊（`concurrency`，不取消進行中的執行） |
| 執行內容 | 只有白名單的 `etl` 指令；爬蟲照常遵守 robots.txt、限速、允許網域、不登入、不繞過封鎖 |

`tests/data/test_data_run.py` 以靜態檢查強制上述 workflow 規則。

## 5. 限制

- `workflow_dispatch` 與排程（`schedule`）只能從預設分支 `main` 執行，`main` 只由專案負責人在階段整合時更新；在那之前用推送觸發。#114 第 6 項（依展期每日排程）需要整合到 `main` 後才能真正每天自動執行。
- Actions 的執行紀錄不是永久保存；結果以 commit 保存在 `data-run/*` 分支，審查後進入 `dev/data-platform`。
