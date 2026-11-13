# 來源快照、擷取批次與錯誤紀錄的保存

> 工作項目：D2-06｜負責人：data｜程式：`crawler/store.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 目錄結構

每次執行（擷取或匯入）一個目錄，**不重用**：

```
<root>/<exhibition_id>/<edition_id>/<crawl_run_id>/
    snapshots/<source_id>.<ext>   原始位元組，原樣保存
    sources.jsonl                 每份快照一筆 source 紀錄（符合 source.schema.json，依 source_id 排序）
    crawl_run.json                crawl_run 紀錄（共用契約）
    run.log.jsonl                 事件日誌（D1-07 格式）
    errors.json                   該次所有錯誤（crawl_run.error_samples 最多只留 50 筆）
```

建議 `<root>` 為 `data/raw`（`root_label` 預設值，寫入 `source.snapshot.locator`，從 repo 根目錄起算）。副檔名依 media type（html、csv、pdf、xlsx、json、xml、txt），未知為 `.bin`。

## 2. 規則

| 規則 | 實作 |
|---|---|
| 證據不可變 | 檔案以獨佔方式建立；已存在即 `StoreError`，不覆寫。同一 `source_id` 不可存兩次，已完成的執行目錄不可再 `finalize` |
| 先存證據 | `RunStore` 就是執行器的 `sink`：每個回應一收到就寫入，**早於解析**，執行中途當掉也不會遺失已取得的內容 |
| 內容與雜湊一致 | 寫入前重新計算 sha256 與大小，不符即拒絕 |
| 路徑安全 | `exhibition_id`、`edition_id` 必須是目錄安全字元；`source_id`、`crawl_run_id` 必須符合 ULID 格式，否則拒絕 |
| 完成標記 | `crawl_run.json` 最後寫入；它存在即代表該目錄完整 |
| Git 不是大型檔案倉庫 | 超過 `max_stored_bytes`（預設 5 MiB）的快照**不存**：`source.snapshot.storage = "not_stored"`，`notes` 說明原因，仍保留 sha256 供日後比對。要保存更大的檔案請刻意調整上限或另選儲存方式（Release、外部），不要誤提交大檔 |

`source` 紀錄：`source_type` 取自來源設定、`url` 為請求網址（重新導向時在 `notes` 記錄最終網址）、`snapshot = {storage: "git", locator: "<root_label>/<路徑>"}`。

## 3. 驗證

`verify_run(run_dir)` 回傳問題清單（空 = 完整）：缺少檔案、快照檔案數量不對、內容與 sha256 不符、沒有 source 紀錄的多餘快照、無法解析的 source 行。未保存的快照（`not_stored`）不要求檔案。

## 4. 使用

```python
store = RunStore("data/raw", config)
result = run_source(config, adapter, fetcher, sink=store)      # 或 import_files(..., sink=store)
run_dir = store.finalize(result)
assert verify_run(run_dir) == []
```

## 5. 不包含

- 把這些檔案提交到 Git、開資料更新 PR（D2-05／D2-13 的 workflow）。
- 把多次執行的 source / crawl_run 彙整進資料包（D2-11）。
- Release、Actions Artifact、外部儲存；保留期限（`retained_until`）管理；壓縮。（資料包層級的快照驗證與備份檔見 D4-03 `integrity-and-backup.md`；保存位置仍未決定。）
- 清理舊的執行目錄（不刪除是刻意的，刪除屬人工決定）。
