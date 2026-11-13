# 資料工程模組回歸測試

> 工作項目：D3-08｜負責人：data｜程式：`tests/data/regression_outputs.py`、`tests/data/test_regression.py`、`tests/data/test_clock.py`｜基準檔：`tests/data/regression/*.json`
> 本文件只記錄已實作並測試過的行為。

## 1. 目的

各模組的單元測試檢查個別規則；回歸測試把**整條資料工程流程的實際輸出**固定下來，任何模組的行為改變（紀錄內容、雜湊、排序、通知文字）都會以基準檔差異的形式出現在 PR 裡，由人審查是否為預期的改變。

## 2. 涵蓋的輸出

全部使用合成資料（`data_origin: "synthetic"`），固定時間與固定 ID 來源；絕對路徑替換為 `<repo>`／`<tmp>`。

| 基準檔 | 產生方式 | 涵蓋模組 |
|---|---|---|
| `samples.json` | `data/samples/build_samples.py` 在暫存目錄重建 3 個樣本資料包：`dataset_id`、`content_hash`、各檔 `sha256`／`bytes`／`records` | `etl.package`、`etl.jsonl`、`etl.hashing`、樣本產生程式 |
| `pipeline.json` | `tests/data/test_assemble.py` 的 CSV 匯入流程（`crawler.file_import` → `crawler.store` → `etl.build_records` → `etl.assemble`），另一份加上官方筆數（completeness `partial`） | `crawler.importers`、`crawler.file_import`、`crawler.store`、`etl.normalize`、`etl.registry`、`etl.build_records`、`etl.assemble` |
| `validate.json` | 3 個樣本的驗證結果 | `etl.validate`、`etl.schema_registry` |
| `dataset_index.json` | 樣本的資料集索引（固定 `generated_at`；先過 IR1–IR7） | `etl.dataset_index` |
| `history.json` | 每屆最新樣本的參展歷史 | `etl.history` |
| `report.json` | 3 個樣本的完整度與品質報告 | `etl.report` |
| `screening.json` | 固定規則（出現 include、excluded、review、unscreened 四種標籤）篩選樣本 v2 | `etl.screening` |
| `catalog.json` | 搜尋（全部、別名）、時間軸、v1→v2 差異 | `etl.catalog`、`etl.changes` |

## 3. 其他檢查（`test_regression.py`）

- 基準檔恰好對應 8 個輸出；基準檔不含機器路徑；`data_origin` 只有 `synthetic`。
- 在另一個工作目錄、另一個行程重新計算，結果相同（不依賴 cwd、暫存路徑或先前的呼叫）。
- `crawler/`、`etl/` 每個模組至少被一個測試 import。這項檢查發現 `crawler.clock`（`SystemClock`）原本沒有測試，已補 `test_clock.py`。
- 每個命令列（`etl.validate`、`etl.report`、`etl.build_index`、`etl.catalog`、回歸工具本身）`--help` 可以執行。

## 4. 操作

```bash
python -m pytest -q tests/data/test_regression.py        # 比對
python -m tests.data.regression_outputs                    # 只比對，結束碼 1 並列出不同的輸出
python -m tests.data.regression_outputs --write            # 預期內的改變：重寫基準檔
git diff tests/data/regression/                            # 審查差異後與程式變更一起提交
```

規則：**只有在改變是刻意的時候才重寫基準檔**，並在 PR 說明差異的原因。Schema 升版時 `samples.json`、`validate.json`、`dataset_index.json` 的 `schema_version` 會改變，屬預期。

## 5. 驗證（2026-11-09，雲端容器，Python 3.11／3.12／3.13）

- 3 個版本、在 repo 以外的工作目錄執行比對，結果相同。
- 植入行為改變（突變）後被抓到：JSONL 分隔符（7 個輸出都變）、`content_hash` 排序、完整度判斷、`official_count_as_of` 欄位名、篩選標籤、索引通知文字、報告缺口文字、catalog 排序、匯入文字清洗。
- 未被回歸測試抓到、但已有單元測試涵蓋的突變：同一企業多筆參展紀錄的歷史排序（樣本中每家只有一筆；見 `test_changes_and_history.py`）、中日韓公司型態去除（樣本沒有 CJK 名稱；見 `test_normalize.py`）。

## 6. 不包含

- 真實資料（目前沒有真實資料包；D2-02／D2-03 之後再加入）。
- 網路取得（`crawler.fetch` 的回歸由 `test_crawler_fetch.py` 以本機伺服器測試）。
- 效能基準。
