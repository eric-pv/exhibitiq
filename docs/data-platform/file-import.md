# 檔案匯入（CSV／HTML 表格／Excel／PDF 文字層）與欄位對應設定

> 工作項目：D2-04｜負責人：data｜程式：`crawler/importers.py`、`crawler/file_import.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 定位

匯入是**正式的取得方式**（`file_import` / `authorized_file`），與網站擷取走同一個執行器（D2-01）：每個檔案產生不可變快照（原始位元組、`sha256:`、時間、`src_` ID）、`crawl_run` 紀錄、結構化錯誤與日誌。新的檔案結構只需要新增**對應設定**，不改程式（V2.3）。

輸出是「如原文所列」的原始欄位（文字、去除前後空白）。空白儲存格**不補值**，該欄位不出現在該列。欄位正規化、去重屬 ETL（D2-07）。

## 2. 對應設定

放在來源設定的 `[options.mapping]`（或獨立 TOML，用 `load_mapping()` 載入）：

```toml
adapter = "file-import"
start_urls = ["https://files.example.com/exhibitors.xlsx"]   # 檔案取得來源的網址，會寫入 source 紀錄
source_type = "excel_import"

[options.mapping]
format = "xlsx"          # csv | html_table | xlsx | pdf_text
header_row = 2           # 1 起算，預設 1
sheet = "List"           # xlsx；預設第一個工作表（多個時會警告）

[[options.mapping.columns]]
source = "Company"                       # 檔案中的表頭（忽略大小寫與多餘空白）
field = "exhibitor_name_as_listed"       # 輸出的原始欄位名稱
required = true                          # 必填欄位為空的列會被略過並警告
```

| 格式 | 可用選項 | 備註 |
|---|---|---|
| `csv` | `encoding`（預設 `utf-8-sig`）、`delimiter` | 編碼不符 → `parse_error`，不猜測 |
| `html_table` | `table_index`（0 起算）、`table_id` | 巢狀表格的內容不併入；`colspan`/`rowspan` 不展開（會警告） |
| `xlsx` | `sheet` | 只讀快取值，**不計算公式**；從未計算過的公式讀成空白 |
| `pdf_text` | `split_pattern`（預設兩個以上空白或 Tab） | 只讀文字層，**不做 OCR**；以文字間距切欄，一律警告「請對照原檔」；欄數不符的行略過並警告 |

規則：
- 必填欄位不在檔案中、表頭重複、`header_row` 超出範圍、檔案無法讀取 → 整個檔案 `parse_error`（快照仍保留）。
- 選填欄位不在檔案中 → 警告，每列都沒有該欄位。
- 重複出現的表頭列（例如每頁重印）不算資料。
- 每列加上 `_row`（來源列號 / 行號 / 表格列號，1 起算）以便追溯；欄位名稱必須是 `^[a-z][a-z0-9_]{0,63}$`，含 `password`、`token`、`secret` 等字樣者拒絕。
- 上限：20 MiB（`max_bytes`）、200,000 列；警告最多 200 則。

## 3. 使用

```python
from crawler.file_import import import_files
result = import_files(config, {"https://files.example.com/exhibitors.xlsx": "inbox/exhibitors.xlsx"})
result.records      # ExtractedRecord：資料 + 來源 ID + 快照雜湊
result.crawl_run    # 符合 crawl_run.schema.json，trigger = "import"
```

`LocalFileFetcher` 以「來源網址 → 本機檔案」提供檔案，**不連網、不查 robots.txt**；檔案網址必須在 `start_urls` 內。檔案若是從網站取得，網址填原始下載網址；Schema 要求非人工輸入的 `source` 都有 `http(s)` 網址。

也可直接透過網址取得檔案：設定 `adapter = "file-import"`，用一般的網頁擷取執行器（D2-01）抓取，同樣套用範圍、頻率、robots.txt 規則。

## 4. 不包含

- 欄位正規化、企業去重（D2-07）；快照落地（D2-06）；Actions 觸發（D2-05、D2-13）。
- OCR、掃描 PDF、PDF 中的複雜表格、合併儲存格展開、`.xls`（舊格式）、多工作表合併。
- 新增依賴：`openpyxl==3.1.5`（含其依賴 `et_xmlfile`）、`pypdf==6.21.4`。
