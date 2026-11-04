# 證據與結論規則

| 情況 | 寫成 | 必要條件 |
|---|---|---|
| 資料包中的來源直接寫明 | `fact` | `evidence_source_ids` ≥1；`verification_status` 沿用資料包紀錄（`verified`／`unverified`／`human_confirmed`） |
| 根據來源推論出來 | `inference` | 來源 ≥1、`rationale`、`confidence`（low／medium／high）、`uncertainty_ids` ≥1 |
| 來源不足以判斷 | `unknown` | `missing_data` 說明缺什麼；**不得猜測** |

## 信心等級
- **high：** 多個獨立來源一致，而且推論只有一小步。
- **medium：** 單一明確來源，或多個來源但需要合理推論。
- **low：** 只有間接線索。
- 不使用百分比。

## 評分（可拆解）
- 每個因子都要有 `max_points`、`points`、`rationale`。
- 有證據時 `status: scored`，並附 `evidence_source_ids`。
- 沒有證據時 `status: insufficient_data`、`points: 0`，**不推估**。
- 同一個評分模型（`score_model_id`，例如 `opportunity@1`）的所有企業使用同一組因子；評分模型的因子與配分見 `knowledge/scoring/opportunity@1.json`（A2-07，草稿待核定）；`exhibitiq_tools.py score` 產生確定性部分，需要閱讀來源的因子（合作或採購訊號）由 Skill 補上並附來源。

## 關係分類
潛在客戶、競爭對手、合作夥伴、通路一律是推論；資料不足時用 `unknown`，不要硬分類。

## 不確定性
資料包完整度不是 `complete`、來源只有參展商自填資料、分類依據薄弱時，都要列出不確定性，並在相關結論與建議中引用。

## 自動驗證（A2-11）
`exhibitiq_tools.py validate-analysis` 使用 `scripts/evidence_check.py`：契約規則 AR1–AR9 加上下列證據規則。**任何一項失敗，分析結果就不能發布**（不得寫入 `reports/analysis/`，Dashboard 也不會顯示）。

| 規則 | 內容 |
|---|---|
| EV1 | `fact` 要有來源與查證狀態、不能有信心等級；查證狀態不得高於資料包中對應紀錄 |
| EV2 | `inference` 要有來源、理由、信心等級、不確定性；不得帶有事實的查證狀態 |
| EV3 | `unknown` 要寫明缺少的資料；不得有信心等級 |
| EV4 | 計分因子要有來源、不得依據 `unknown` 結論；資料不足的因子一律 0 分 |
| EV5 | 潛在客戶／競爭對手／合作夥伴／通路分類要有來源與信心等級 |
| EV6 | 輸入資料包不完整時，必須列出不確定性，每個建議都要引用 |
| EV7 | 每個建議都要有來源 |
