# 以 GitHub Actions 手動或排程執行擷取／匯入

> 工作項目：D2-05｜負責人：data｜程式：`crawler/cli.py`、`crawler/resume.py`、`.github/workflows/crawl.yml`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含與尚未驗證」。

## 1. 流程

```
Actions → crawl → Run workflow（來源名稱、最多頁數、續跑 ID）
   → plan：決定要跑哪些來源（手動：輸入的那一個；排程：crawler/schedule.toml）
   → crawl（每個來源一個、依序執行）：python -m crawler.cli run …
   → 證據推到 data/crawl-<來源>-<run_id> 分支，開 PR 到 dev/data-platform（合併人：Albert）
```

- **永遠不寫入 `main`**；也不直接推 `dev/data-platform`。資料經 PR 進入，由 Albert 審閱與合併。
- 狀態是 `failed`／`partial` 也會提交：失敗是資料。PR 內容寫明狀態、快照數、錯誤數、未抓取數。
- 限速、重試、退避來自**來源設定**（`rate_limit_per_second`、`max_retries`、`timeout_seconds`）；頁數上限是 workflow 輸入 `max_requests`（1–5000，預設 500）。

## 2. 命令列

```
python -m crawler.cli run --source NAME [--max-requests N] [--resume RUN] [--out data/raw] [--trigger manual|schedule]
python -m crawler.cli scheduled
```

輸出 `key=value`：`status`、`run_dir`、`crawl_run_id`、`snapshots`、`errors`、`pending`。結束碼 `0` = 執行已記錄（不論 `status`）；`2` = 要求本身無效（名稱不合法、設定錯誤、找不到適配器、無可續跑），**什麼都沒執行也沒寫入**。

輸入視為不可信（來自 workflow 輸入）：名稱只允許小寫英數與連字號；設定檔必須在 `crawler/sources/` 內（含符號連結檢查）且 `name` 等於檔名；`--resume` 只接受 `--out` 底下的執行。

## 3. 續跑

續跑是**新的一次執行**（新 `crawl_run_id`、新快照），`notes` 寫「resumes run_…」；它不會重抓前次已成功的頁面，也不改動前次目錄。展覽的資料是各次執行的聯集（彙整屬 D2-11）。

續跑抓：前次的 `pending.json`（找到但沒抓：`max_requests`、取消）＋暫時性錯誤（`network_error`、`timeout`、5xx 的 `http_error`）。
**不續跑**：`access_blocked`（robots.txt 禁止的網址仍跳過；網站回 401/403/429 的來源**整個拒絕續跑**，必須先回頭看來源評估）、`config_invalid`、`parse_error`、`unexpected`、回應過大。

## 4. 排程

`crawler/schedule.toml` 的 `sources = [...]` 決定排程跑哪些來源，**預設為空，所以排程目前什麼都不抓**。加入來源前先完成來源評估。排程固定每週一 03:17 UTC，且只在預設分支上的 workflow 檔才會觸發（見下）。

## 5. 安全設計（有測試保護）

- 預設權限為空；只有 `crawl` 工作有 `contents: write` 與 `pull-requests: write`，`plan` 只有 `contents: read`。
- 輸入只經 `env` 進入 shell，不插入指令；來源名稱與續跑 ID 再由程式驗證。
- 每個來源一個 `concurrency` 群組（不取消進行中的執行）、來源依序執行（`max-parallel: 1`）、工作逾時、無密鑰、不使用憑證。
- 不使用 `pull_request_target`、`workflow_run` 等會用高權限執行外部程式碼的觸發方式。
- `.github/workflows/` 內每個 workflow 都被 `tests/data/test_workflows.py` 檢查（空預設權限、逾時、只用已知 actions、無危險觸發、無推到 main）。

## 6. 不包含與尚未驗證

- **這個 workflow 尚未在真實的 GitHub Actions 上執行過**；測試只做靜態檢查，CLI 以假抓取器測試。第一次使用請先手動跑一個來源並檢查 PR。
- 開 PR 需要在 repo 設定開啟「Allow GitHub Actions to create and approve pull requests」。這是 repo 設定，我不能也不應修改。
- 排程只會在預設分支（`main`）上有此檔案時觸發；在階段整合前，只能用手動觸發（選 `dev/data-platform` 分支）。
- actions 以主版本標籤（`@v4`、`@v5`）引用，未釘到 commit SHA（離線環境無法查證 SHA）；有需要可日後釘選。
- 目錄 `crawler/sources/` 目前沒有任何來源設定（V2.3：不預設任何展覽）；來源由來源評估後再新增。
- 新增依賴 `PyYAML==6.0.3`（僅測試用）。
