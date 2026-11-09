# 從一個檔案到資料包：`etl.import_file` 與 `printed-listing` 適配器

> 工作項目：D2-02（第一份真實資料）｜負責人：data｜程式：`etl/import_file.py`、`crawler/printed_listing.py`
> 測試：`tests/data/test_import_file.py`、`tests/data/test_printed_listing.py`、`tests/data/test_collected_packages.py`
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

## 3. 已提交的真實資料（`data_origin: collected`）

`tests/data/test_collected_packages.py` 對 `data/packages/` 下每個資料包檢查：通過驗證、快照存在且雜湊正確、可逐位元組重新產生；若 `data/sources/` 有該屆的來源設定，**從快照重新解析的名單必須與資料包相同**；完整度與官方筆數一致；索引的 `latest_dataset_id` 指向每屆最新的資料包。

目前：IACP 2026（662／662，`complete`），來源評估見 `iacp-2026-source-assessment.md`。

## 4. 限制

- 名稱經 `etl.normalize.clean_text`（NFKC）存入 `exhibitor_name_as_listed`，例如「™」變「TM」、全形括號變半形（D2-07 既有行為）；原文在快照中。
- 一次一個檔案；多檔來源請分次匯入（每次都會攜帶前一包）。
- 沒有 Actions workflow（D2-05／D2-13 為還原狀態）。
