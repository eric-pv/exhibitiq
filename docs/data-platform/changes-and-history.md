# 跨年度變更比對與參展歷史

> 工作項目：D2-08｜負責人：data｜程式：`etl/changes.py`、`etl/history.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 同一屆再次取得：`carry_forward`

資料包不可變（契約 §3）。同一屆重新取得時，新資料包由新的取得結果建構（`build_records`），再與前一個資料包合併：

| 情況 | 結果 |
|---|---|
| 前次 `listed`、本次名單沒有 | 保留，`listing_status: "removed"`，`notes` 補一句說明；`last_seen_at` 維持前次 |
| 前次 `removed`、本次又出現 | 變回 `listed`（記為一筆 modified） |
| 前次 `removed`、本次仍沒有 | 原樣保留，不產生變更 |
| 公司 | 保留到仍被參展紀錄或「被保留公司的 `merged_into`」引用為止；其餘丟棄並警告 |
| `first_seen_at` | 取較早者（歷史不被改寫） |
| 人工標記 `merged` 的公司 | 沿用前次紀錄（`merged_into` 不被新建構悄悄取消），並警告 |
| `sources`、`crawl_runs` | 累積前次與本次，依主鍵排序，確保被攜帶的紀錄的參照都成立（R10） |

輸入不被修改。

## 2. 變更紀錄：`diff_records`

逐欄「字面」比較前後兩組 `companies` / `participations`，產生符合 `change.schema.json` 的紀錄：

- `added`、`removed`（`listed` → `removed`）、`modified`（附 `field_changes`，`before`/`after` 為完整值，巢狀欄位整個比較）。
- **前次有、現在沒有的欄位 → `after: null`**（意思是「最新名單沒有這個欄位」，不做詮釋）。
- 不比較 `source_ids`、`field_sources`、`last_seen_at`（書記欄位）。`notes` 會比較。
- 第一個資料包沒有前次，`changes.jsonl` 必須為空，驗證程式強制。
- 以 D1-06 範例資料包的 v1→v2 驗證：找到的變更與範例手寫的變更一致（扣除自由文字 `notes` 的差異）。

## 3. 跨展會／跨年度歷史：`etl/history.py`

`latest_package_dirs(root)` 對每個 `<展覽>/<年>` 取 `dataset_id` 最大（最新）的資料包；`build_history()` 逐包驗證（R1–R11）後彙整為 `company_id → 參展歷史`：

```json
{"version": 1, "datasets": [...], "companies": {"co_…": {"name": "…", "participations": [
   {"exhibition_id": "…", "edition_id": "…", "edition_year": 2026, "dataset_id": "…", "data_origin": "synthetic",
    "participation_id": "pt_…", "listing_status": "listed", "exhibitor_name_as_listed": "…", "booth": "…", "canonical_company_id": "co_…"}]}},
 "skipped": [{"path": "…", "reason": "…"}]}
```

- 驗證失敗或無法讀取的資料包列入 `skipped` 並寫明原因，不被默默忽略，也不被使用。
- 每筆保留 `data_origin`，合成資料不會被誤當成真實資料。
- 已被人工合併的公司會附 `canonical_company_id`（沿 `merged_into` 追到最後，循環時停止）；原本的 ID 保留。
- `History.save()` 原子寫入。慣例位置 `data/history/companies.json`。

## 4. 完整流程（測試中端對端執行）

第一次取得 → `assemble_package` → 第二次取得 → `build_records`（同一個登錄表，ID 穩定）→ `carry_forward` → `diff_records` → `assemble_package(previous_dataset_id=…, changes=…)`，通過驗證程式。

## 5. 不包含

- 人工合併流程（決定 `merged`）；`carry_forward` 只尊重已存在的決定。
- 展覽或屆次紀錄（`exhibition` / `edition`）本身的欄位變更比對。
- 跨屆次的「同一屆多個資料包」歷史瀏覽（只用每屆最新的）；歷史索引的發布與 Dashboard 讀取（D2-12、D3-04）。
- 官方筆數與完整度報告（D2-09）。
