# 從一個檔案到資料包：`etl.import_file` 與 `printed-listing`、`pdf-layout-table` 適配器

> 工作項目：D2-02（第一份真實資料）、D2-03（第二個不同結構）｜負責人：data｜程式：`etl/import_file.py`、`crawler/printed_listing.py`、`crawler/pdf_layout_table.py`
> 測試：`tests/data/test_import_file.py`、`tests/data/test_printed_listing.py`、`tests/data/test_pdf_layout_table.py`、`tests/data/test_collected_packages.py`
> 本文件只記錄已實作並測試過的行為。

## 1. `python -m etl.import_file`

把一個檔案走完整條流程，每一步都是既有模組本身的行為：

1. `crawler.file_import.import_files`（依來源設定選適配器）＋ `crawler.store.RunStore`：檔案先存成不可變快照（`--raw`，預設 `data/raw`），`verify_run` 檢查。**之後任何一步停下來，證據都保留。**
2. `etl.build_records`，使用企業登錄表（`--registry`，預設 `data/registry/companies.json`，不存在時建立）。
3. 該屆已有通過驗證的資料包時：`carry_forward`＋`diff_records`，新資料包指向前一包。
4. `etl.quality.check_acquisition`：有阻擋項就停止（結束碼 1），不發布、不存登錄表；人確認後可加 `--accept Q3`。
5. `etl.assemble.assemble_package`（發布前先驗證 R1–R11），成功後才存登錄表。

```bash
python -m etl.import_file --config data/sources/<exhibition_id>/<edition_id>.toml --file <檔案> \
  --info data/sources/<exhibition_id>/<edition_id>.info.json \
  [--official-count N --official-as-of YYYY-MM-DD] [--notes "取得方式"] [--accept Q3] [--created-at 2026-11-09T08:00:00Z]
python -m etl.build_index      # 之後重建資料集索引
```

- `--info`：`{"exhibition": {...}, "edition": {"year": 2026, ...}}`。**每個值都必須是匯入的檔案本身寫的**；兩筆紀錄只引用該檔案（`source_ids`），標為 `unverified`。不能自己設 `source_ids`、`verification_status`、ID。
- `--official-count`：同一檔案寫的展商總數。沒有就不要給（完整度會是 `unknown`）。
- `--origin`：檔案的取得網址，預設為來源設定的第一個 `start_urls`。
- `--country-aliases`：`{"檔案中的國家寫法": "ISO 3166-1 alpha-2"}`。國家寫法因來源而異，屬來源的對應設定（D2-07 不內建猜測）；表中沒有的寫法只保留在 `country_as_listed`。
- 結束碼：0 已寫出資料包；1 品質關卡阻擋或建構失敗（證據保留、未發布）；2 輸入錯誤。

## 2. `printed-listing` 適配器

用瀏覽器把「展商名單頁」另存成 PDF 時，很多名單平台的每一筆會長這樣（文字層）：

```text
<logo 替代文字> <名稱><攤位>      或      <名稱>
<名稱>                                    <攤位>
                                          <名稱>
```

名稱單獨重複出現的那一行就是一筆的結尾；名稱太長而換行時跨行比對。程式不含任何網站名稱，差異都放在來源設定的 `[options]`：

| 選項 | 必填 | 內容 |
|---|---|---|
| `section_heading` | 是 | 要讀的段落標題的正規表示式；具名群組 `count` 取得頁面宣稱的筆數 |
| `stop_heading` | | 段落結束的標題 |
| `ignore_lines` | | 頁首頁尾等每頁重複的行（正規表示式） |
| `detail_field` | | 細節行放進的原始欄位，預設 `booth` |

讀到的筆數與標題宣稱的不同、或段落後有無法歸為一筆的文字，都會產生警告（不隱藏）；找不到段落標題、沒有任何一筆、PDF 加密或沒有文字層 → `parse_error`（快照仍保留）。不做 OCR。

## 3. `pdf-layout-table` 適配器

主辦單位公布的 PDF 表格名單，文字層常常沒有欄位分隔，長儲存格換行，而且多行儲存格**垂直置中**（三行名稱的第一行在列號上方）。逐行讀文字無法判斷某一行屬於哪一列，所以這個適配器讀每段文字在頁面上的座標：

1. **列**：以最左欄符合 `row_number`（預設 `^\d+$`）的文字為錨點；其他文字歸到垂直距離最近的錨點，超過 `max_row_offset`（預設 14 pt）的不屬於表格（標題、頁碼），不在 `ignore_text` 中的會產生警告。
2. **欄**：全文件中最常用的水平起點，彼此至少相隔 `min_column_gap`（預設 20 pt）；緊接在同一行前一段文字之後（一個字寬內）的片段不算欄位起點。每段文字歸到它左邊最近的欄。
3. **接字**：同一儲存格由上到下、由左到右；同一行的片段只在頁面上真的有間隔（依字型的 `/Widths` 算出前一段的結束位置；沒有字寬表時以每字 0.5 em、全形字 1 em 估算）或原文帶空白時補空白；換行補空白，但行尾是 `-`、`，`，或前一行整行沒有空白（長字被強制斷開）時不補。
4. 列號不連續、沒有名稱的列都會警告。拒絕加密 PDF，不做 OCR。

| 選項 | 必填 | 內容 |
|---|---|---|
| `columns` | 是 | 由左到右的原始欄位；列號欄為 `_number`（必須最左），`_skip` 丟棄該欄 |
| `ignore_text` | | 表格外預期會出現的文字（標題、表頭、頁碼、更新日期） |
| `row_number` | | 列號的正規表示式 |
| `max_row_offset`、`min_column_gap` | | 見上 |

## 4. 已提交的真實資料（`data_origin: collected`）

`tests/data/test_collected_packages.py` 對 `data/packages/` 下每個資料包檢查：通過驗證、快照存在且雜湊正確、可逐位元組重新產生；若 `data/sources/` 有該屆的來源設定，**從快照重新解析的名單必須與資料包相同**（名稱比對鍵相同；每種拼法都完整出現在參展名稱或企業別名中；每個攤位都在攤位或備註中）；完整度與官方筆數一致；索引的 `latest_dataset_id` 指向每屆最新的資料包。

目前：

| 屆次 | 結構 | 適配器 | 結果 | 來源評估 |
|---|---|---|---|---|
| IACP 2026 | 瀏覽器列印的名單頁 | `printed-listing` | 662／662，`complete` | `iacp-2026-source-assessment.md` |
| DSA 2026 | 主辦單位 PDF 表格（5 欄、多行置中） | `pdf-layout-table` | 1184 列 → 1172 筆，`unknown`（無宣稱總數） | `dsa-2026-source-assessment.md` |

兩個展覽共用企業登錄表：同名公司在兩屆拿到同一個 `company_id`（目前 11 家），可做跨展覽比較。

## 5. 限制

- 名稱經 `etl.normalize.clean_text`（NFKC）存入 `exhibitor_name_as_listed`，例如「™」變「TM」、全形括號變半形（D2-07 既有行為）；原文在快照中。
- 一次一個檔案；多檔來源請分次匯入（每次都會攜帶前一包）。
- 沒有 Actions workflow（D2-05／D2-13 為還原狀態）。
