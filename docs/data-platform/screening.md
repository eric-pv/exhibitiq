# 初步規則篩選（不刪除原始資料）

> 工作項目：D2-10｜負責人：data｜程式：`etl/screening.py`

規則放在 TOML 設定（程式與展覽、領域無關；關鍵字是設定）：`name` 與多個 `[[rules]]`（`id`、`field`、`op`、`terms`、`outcome`，欄位可用 `company.<欄位>`）。`op`：`contains_any`（子字串，不分大小寫）、`equals_any`（完全相同）、`present`、`absent`；`outcome`：`include`、`exclude`、`review`。

每筆參展紀錄得到一個標籤與命中的規則：

| 標籤 | 條件 |
|---|---|
| `include` | 命中 include 規則，且沒有 exclude／review |
| `excluded` | 命中 exclude 規則，且沒有 include／review |
| `review` | 命中 review 規則，或 include 與 exclude 同時命中（交給人判斷） |
| `unscreened` | 沒有命中任何規則 |

**不刪除、不修改：** 資料包與輸入紀錄完全不動，`excluded` 仍出現在輸出與所有匯出中。輸出（`screen_package`）註明 `kind: rule_based`、「不是 AI 判斷也不是已查證事實」，並含規則內容與指紋以便重現；`save_screening` 原子寫入（建議 `data/screening/<dataset_id>.json`）。

不包含：AI 分類與評分（AI 側）、規則編輯介面、把標籤寫進資料包（Schema 不允許額外欄位）。
