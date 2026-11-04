# 資料集索引與管線狀態（Dashboard 讀取的檔案）

> 工作項目：D2-12｜負責人：data｜程式：`etl/dataset_index.py`、`etl/build_index.py`
> 契約：`docs/specs/dataset-index-contract.md`（A1-07）。本文件只記錄已實作並測試過的行為。

## 1. 位置與流程

`python -m etl.build_index` 掃描 `data/packages/<展覽>/<年>/<dataset_id>/`，逐包執行驗證程式（R1–R11），寫出 **`data/index/datasets.json`**（Eric 的 Dashboard bundle 程式優先讀這個檔，沒有才用範例）。寫入前先過 IR1–IR7，不合格就不寫（結束碼 2）；原子寫入。

| 輸入 | 來源 |
|---|---|
| 資料包 | `--packages`（預設 `data/packages`） |
| 取得方式與來源評估 | `--assessments`（預設 `data/index/assessments.json`，`{exhibition_id: {name, method, status, assessed_at, report_path, notes}}`，來源評估後由人寫入；**缺的展覽記為 `undetermined` / `not_assessed`，不假設可行**） |
| 沒有進入任何資料包的取得結果（常是失敗） | `--runs-dir`（預設 `data/raw`，`crawler.store` 的目錄；其中 `crawl_run.json` 不在任何資料包的 `crawl_run_ids` 內者） |

## 2. 內容規則

- 每個展覽：資料包內 `exhibition.json` 的名稱／國家／網站＋取得評估；每個屆次：所有資料包摘要（數值與 manifest 相同）、`latest_dataset_id`、`last_acquisition`。
- **`latest_dataset_id` 是驗證通過、`created_at` 最新者**。驗證失敗的資料包仍列出（附最多 20 筆 `messages`）並產生 error 通知，但絕不會成為 latest；讀不出來的目錄產生 error 通知並略過。
- `last_acquisition`：取該屆最新完成的擷取批次（含失敗）；`failed` 一定有 `notes` 且沒有 `dataset_id`；`partial`／`cancelled` 也附原因；成功／部分成功指向包含該批次的最新通過資料包。後來的失敗不會推翻先前通過的資料包。
- 通知：取得失敗（warning）、驗證失敗（error）、完整度不是 `complete`（info，說明官方筆數／收集數或「沒有官方筆數」）。
- `validate_index()` 實作 IR1–IR7（IR2 由 Schema 的 `const` 強制）；IR6 會重新驗證標為 `passed` 的資料包，並比對摘要與 manifest。

## 3. 不包含

- 發布到 GitHub Pages 或外部儲存（Eric 的決定事項）、資料包 Release 打包、Actions 排程（D2-05 目前為還原狀態，見 PR #48）。
- 來源評估報告本身（人工撰寫，`report_path` 指向它）。
