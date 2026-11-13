# 資料包搜尋、屆次時間軸與歷史差異（唯讀工具）

> 工作項目：D3-04｜負責人：data｜程式：`etl/catalog.py`｜測試：`tests/data/test_catalog.py`
> 依賴：D2-08（`etl/changes.py`、`etl/history.py`）、D2-12（資料集索引）。本文件只記錄已實作並測試過的行為。

## 1. 用途與界線

給維護者、Actions 與 Skill 在雲端工作區直接查詢 `data/packages/` 的**唯讀**工具。不寫入、不修改任何資料包（測試逐位元組確認）。

- 輸出是 JSON（`version: 1`、`kind: search|timeline|diff`），**不是共用契約**：`schemas/` 沒有對應 Schema，Dashboard 不應依賴這個格式。Dashboard 的展覽搜尋讀 `data/index/datasets.json`（D2-12），企業搜尋在前端做（W2-02）。
- 只用**驗證通過（R1–R11）**的資料包。未通過的列在 `skipped`／`notices` 並寫明原因，不讀它的內容，也不用較舊的資料包悄悄代替。
- 每筆結果帶 `data_origin`；結果是從資料包複製的事實，不評分、不推論。

## 2. 指令

```bash
python -m etl.catalog search  [--packages data/packages] [QUERY] [--country ZZ] [--exhibition ID] [--year 2026] [--status listed|removed]
python -m etl.catalog timeline [--packages data/packages] EXHIBITION_ID YEAR
python -m etl.catalog diff OLDER_PACKAGE_DIR NEWER_PACKAGE_DIR
```

結束碼：0 完成（JSON 寫到 stdout）、2 輸入錯誤（訊息寫到 stderr）。

## 3. `search`：跨展會企業搜尋

- 範圍：每個 `<展覽>/<年>` 的**最新**資料包（`etl.history.latest_package_dirs`，`dataset_id` 最大者）；Python 呼叫可改傳資料包目錄清單。
- 比對欄位：`name`、`name_zh_hant`、`aliases[].name`、`company_id`（完全相同）、`website` 主機名與 `domains`（完全相同，忽略 `www.`）。
- 名稱比對用 `etl.normalize.name_keys`（與企業登錄表相同的鍵）：忽略大小寫、全形／半形（NFKC）、標點與空白、結尾的公司型態（Ltd、Inc、股份有限公司…）。命中條件：查詢的完整鍵是候選完整鍵的子字串，或兩者去除公司型態後相同。
- 不做模糊或相似度比對；主機名必須相同（`ample.org` 不會命中 `example.org`）。
- 篩選：`--country`（企業 `country`）、`--exhibition`、`--year`、`--status`（參展紀錄 `listing_status`）。
- 每家企業：`company_id`、`name`、`country`／`website`／`status`／`merged_into`（有才列）、`matched_on`（命中哪個欄位與值）、`participations`（展覽、屆次、年份、`dataset_id`、`data_origin`、`participation_id`、`listing_status`、名單上的名稱、`source_ids`、攤位／展館）。依名稱（不分大小寫）、`company_id` 排序。

## 4. `timeline`：同一屆所有資料包

`data/packages/<展覽>/<年>/` 下每個資料包，依 `dataset_id` 由舊到新：`created_at`、`data_origin`、`previous_dataset_id`、`record_counts`、`completeness_status`、官方筆數／收集數、`recorded_changes`（`changes.jsonl` 依 company／participation × added／modified／removed 計數）。`latest_valid_dataset_id` 是驗證通過且 `created_at` 最新者（與 D2-12 索引的 `latest_dataset_id` 規則相同）。

只回報、不修復的 `notices`：

| 情況 | 訊息 |
|---|---|
| 資料包驗證失敗 | `<目錄>: fails validation (...); not used in the history` |
| 不是第一個，但 `previous_dataset_id` 為 null | `history restarts here` |
| 指向這一屆不存在的資料包 | `is not a package of this edition` |
| 指向驗證失敗的資料包 | `previous_dataset_id <id> fails validation` |
| 指向較新的資料包 | `is not older` |
| 跳過中間的資料包 | `skips <id>` |
| 目錄名稱與 manifest `dataset_id` 不同 | `directory name differs` |

## 5. `diff`：任兩個資料包的差異

- 兩個資料包都必須驗證通過、同一屆（`edition_id` 相同），且舊的在前；否則結束碼 2。
- 以 `etl.changes.diff_records` 重新計算（逐欄字面比較；`source_ids`、`field_sources`、`last_seen_at` 不比較；`notes` 會比較）。
- 輸出 `summary`（計數）與 `changes`（`entity_type`、`entity_id`、`change_type`、`field_changes`、`source_ids`）。**不產生** `change_id`、`detected_at`：這是查詢結果，不是新的變更紀錄，避免發明 ID 或時間；相同輸入輸出相同。
- 新資料包的 `previous_dataset_id` 就是舊資料包時，另附 `recorded_comparison`：以（實體類型、實體 ID、變更類型）比對重新計算與 `changes.jsonl`，列出 `only_recomputed`、`only_recorded`。欄位層級不比對（人工寫的變更紀錄可能省略 `notes` 等自由文字欄位的變動，見 `changes-and-history.md` §2）。

## 6. 驗證（2026-11-09，雲端容器，Python 3.11／3.12／3.13）

- `tests/data/test_catalog.py` 31 個測試，使用 `data/samples/`（合成資料）與由它改寫、重新計算完整性的資料包。
- 樣本 v1→v2 的 `diff` 與 `changes.jsonl` 完全一致（`only_recomputed`、`only_recorded` 皆空）。
- 突變測試 26 個（忽略驗證失敗、關閉別名／中文名／ID／網域比對、改成相似度主機比對、關閉各篩選、關閉各項鏈檢查、選錯 latest、關閉 diff 的輸入檢查、對調比對結果、保留隨機 ID 等）全部被測試抓到。

## 7. 不包含

- 全文或模糊搜尋、排名、拼字建議。
- 展覽或屆次紀錄（`exhibition`／`edition`）本身的欄位差異。
- 跨屆次的差異（不同 `edition_id` 的參展紀錄 ID 不同，比較沒有意義；跨屆次的企業歷史用 `etl.history`）。
- 把結果寫成檔案或發布；需要時再由使用的工作項目決定位置。
