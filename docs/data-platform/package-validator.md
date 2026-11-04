# 資料包驗證器

> 工作項目：D1-05｜負責人：data｜程式：`etl/validate.py`、`etl/schema_registry.py`
> 依據：`docs/specs/data-package-contract.md` §12（規則 R1–R11）、Schema `1.0.0-draft.3`。本文件只記錄已實作並測試過的行為。
> 這是專案**唯一**的資料包驗證程式（`module-boundaries.md`）。`skills/` 或其他模組需要驗證時，呼叫它，不另寫一套。

## 1. 使用

```bash
python -m etl.validate data/packages/<exhibition_id>/<year>/<dataset_id>
python -m etl.validate <dir> --json          # 機器可讀報告
python -m etl.validate <dir> --schemas DIR   # 指定 Schema 目錄（預設 schemas/v1）
```

結束碼：`0` 全部通過、`1` 有違規、`2` 無法執行（例如找不到 Schema）。

```python
from etl.validate import validate_package
report = validate_package(package_dir)   # 不會因為壞資料而拋出例外
report.ok; report.findings; report.rules()   # Finding(rule, message, file, line)
```

## 2. 規則

結構由 `schemas/v1/` 的 Schema 檢查；Schema 表達不了的跨紀錄規則由本程式檢查。

| 規則 | 檢查內容 |
|---|---|
| R1 | 8 個檔案（`manifest.json` 與 7 個資料檔）全部存在 |
| R2 | `manifest.json` 可讀，且通過 `manifest.schema.json` |
| R3 | `schema_version` 與 `schemas/v1/VERSION` 完全相同（草案期） |
| R4 | 每筆紀錄通過對應的 Schema；`exhibition.json`、`edition.json` 各剛好 1 筆 |
| R5 | UTF-8 無 BOM、LF、結尾換行、無空白行、無重複的物件鍵、無 NaN；每行是 canonical 形式 |
| R6 | JSONL 主鍵不重複，且依 UTF-8 位元組順序遞增 |
| R7 | `record_counts` 與各 JSONL 的行數相同 |
| R8 | `files` 的 `sha256`、`bytes`、`records` 與實際檔案相同；`content_hash` 重新計算後相同 |
| R9 | `exhibition.json`、`edition.json` 的 ID 與年份和 manifest 一致；`dataset_id` 以 `<edition_id>.` 開頭 |
| R10 | 參照完整性：所有 `source_ids`、`field_sources`、別名來源（含展覽、屆次、企業、參展紀錄、變更紀錄）都在 `sources.jsonl`；`source_snapshot_ids`、`crawl_run_ids` 與對應檔案的 ID 集合相同；`participation.company_id`、`merged_into` 在 `companies.jsonl`；`source.crawl_run_id` 在 `crawl_runs.jsonl`；參展紀錄與擷取批次的 `edition_id` 與 manifest 相同；變更紀錄的 `dataset_id`、`previous_dataset_id` 與 manifest 相同；第一個資料包（`previous_dataset_id` 為 null）的 `changes.jsonl` 必須為空 |
| R11 | `collected_participation_count` 等於 `listing_status: "listed"` 的參展紀錄數；`official_count_source_id` 存在於 `sources.jsonl`；`completeness_status: "complete"` 時官方筆數等於已列出的參展紀錄數；**官方筆數非 null 時必須有來源**（契約 §9） |

## 3. 行為

- **一次回報所有違規**，不是只回報第一個；每筆含規則編號、檔案，已知時含行號。輸出順序固定（相同輸入、相同輸出）。
- **不因壞檔案崩潰。** BOM、非 UTF-8、無效 JSON、manifest 型別錯誤等，都變成 R5 或 R2 的發現。
- **不產生連帶雜訊。** 單筆檔案（`exhibition.json`、`edition.json`）筆數不對時只報 R4，不再因為資料缺席而多報 R9。
- 某個資料檔因序列化錯誤（R5）無法解析時，該檔案跳過其他規則；缺少任一檔案（R1）時，其餘規則不執行。
- **從本機載入 Schema，不使用網路**：以各檔的 `$id` 建立 `referencing` registry，測試會攔截 socket 確認沒有連線。
- 不使用 `format` 檢查套件；日期與時間以 Schema 的 `pattern` 為準（契約 §12）。

## 4. 驗證結果（2026-11-04，雲端容器）

| Python | 結果（全新 venv，只用 `requirements.txt` 安裝） |
|---|---|
| 3.11 | 219 passed |
| 3.12 | 219 passed |
| 3.13 | 219 passed |

- **正向向量：** 契約的範例資料包 `schemas/v1/examples/package/` 0 違規；用 D1-04 工具重新產生的版本、含變更紀錄的第二版資料包、有已下架參展紀錄的資料包也都通過。
- **反向向量：** 每條規則 R1–R11 都有案例，每個案例斷言**剛好**回報該規則（不多不少）；R1 的 8 個檔案各自缺失都測。共 49 個資料包案例。
- **突變測試：** 故意改壞驗證器 36 處（每條規則的每個檢查各一），全部被測試抓到。第一輪（34 處）有一處漏掉（`exhibition.json` 的 ID 檢查：原案例同時改了兩個檔案，拿掉其中一個檢查結果集合不變），已補上能單獨隔離每個檔案的案例並斷言被標出的檔案。
- **與 `ai` 分支參考檢查交叉比對：** Eric 在 `tests/contract/package_check.py` 有一份獨立寫的參考檢查（只讀，未使用）。對同樣 49 個反向資料包，兩邊回報的規則集合 41 個相同；8 個不同都有原因：

  | 差異 | 原因 |
  |---|---|
  | 4 個（BOM、空白行、無效 JSON、非 UTF-8） | 參考檢查遇到壞檔案時例外崩潰；本驗證器回報 R5 |
  | 2 個（單筆檔案筆數不對） | 參考檢查多報連帶的 R9；本驗證器只報 R4 |
  | 1 個（重複的 JSON 鍵） | 兩邊都標 R5，參考檢查另因取最後一個值而多出 R4、R10 |
  | 1 個（官方筆數非 null 但來源為 null） | **本驗證器依契約 §9 強制，參考檢查沒有檢查**；見「需要專案負責人知道的事」 |

## 5. 需要專案負責人知道的事

1. **R11 比參考檢查多一條。** 契約 §9 寫「官方筆數必須有來源，否則為 null」，但 `manifest.schema.json` 允許 `official_exhibitor_count` 非 null 而 `official_count_source_id` 為 null。本驗證器依契約文字判為違規。若 Eric 認為 Schema 的寬鬆是有意的，請告知，我再調整。
2. **`tests/contract/package_check.py` 檔頭說明「驗證程式完成後，這些測試應改為呼叫它」。** 驗證器已完成；該檔屬 `ai`，我不修改。階段整合時可評估是否改用 `etl.validate`（兩邊在 41／49 個案例上一致，差異如上表）。
3. 本驗證器依賴 `referencing`，已在 `requirements.txt` 明確固定（`0.37.0`）。

## 6. 未涵蓋與限制

- **契約 §3 的「`companies.jsonl` 只收錄本屆有參展紀錄、或被 `merged_into` 參照的企業」不在 R1–R11 內，未檢查。**
- 「核心資料不得出現 `ai_inferred`」（§8）只靠 Schema 的 enum 阻擋，沒有額外規則。
- 只檢查序列化、結構與一致性，**不判斷資料是否真實**；`verification_status` 的值是否恰當不在範圍內。
- 不檢查 `source.content_sha256` 是否對應實際快照（快照可能在 Git 之外），也不檢查 `snapshot.locator` 是否存在。
- 缺少任一檔案時只報 R1，不繼續其他規則；序列化錯誤的檔案不會同時顯示其內容層級的錯誤。
- 每次呼叫都重新載入並檢查 Schema（實測約 0.13 秒）；一次驗證大量資料包時再考慮快取。
