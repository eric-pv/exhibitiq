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

## 趨勢與跨展覽比較（A2-09）
- `exhibitiq_tools.py compare <package_dir>... --profile <主題>` 產生確定性的比較資料：各資料包的完整度、實際取得的企業數、每個啟用關鍵字命中的企業與來源、跨資料包重複出現的企業、依年份排列的關鍵字序列。
- **資料不完整時不計算比例**（`share: null`），只列實際取得的家數；報告要說明完整度的影響。
- 沒有同一展覽的多個年度時，只能寫「跨展覽比較」，**不得宣稱時間趨勢**（`trend_note`），寫成 `unknown` 或不確定性。
- 趨勢結論一律是 `inference`，引用各資料包中命中的來源；數字只能來自 `compare` 的輸出。

## 展覽商務價值與參展建議（A2-10）
- `exhibitiq_tools.py value <package_dir> --profile <主題>` 產生確定性的輸入：主題相關企業家數（資料不完整時不算比例）、各關係候選家數、依評分排序的拜訪候選、完整度與注意事項。
- 參展建議（`participation_decision`）與拜訪建議（`visit_priority`）一律是 AI 推論，必須引用評分（`score_ids`）或結論，並列出不確定性。
- **只評估展覽的商務價值，不評估預算或任何金額**（Eric 2026-11-05）；建議中出現金額、幣別或「預算」會被 EV8 擋下。

| 規則 | 內容 |
|---|---|
| EV8 | 建議不得包含預算或金額；參展建議必須引用評分或結論 |

## 品質檢查（A3-03）
`exhibitiq_tools.py quality <analysis.json> <package_dir>` 使用 `scripts/quality_check.py`，找出**已通過 EV1–EV8、但品質不足**的地方。品質警告**不阻止發布**，但送審前必須修正，或在理由／不確定性中說明為什麼保留。

| 規則 | 內容 |
|---|---|
| QC1 | 拜訪（`visit_priority`）或合作（`partnership`）建議沒有指定企業，無法執行 |
| QC2 | 產品建議（`exhibit_product`）沒有指定產品 |
| QC3 | 分析有評分，但高優先度拜訪建議沒有引用評分 |
| QC4 | 高優先度建議依據的評分有一半以上因子資料不足 |
| QC5 | 優先度與評分相反：優先度較高的拜訪建議，引用的評分比例較低 |
| QC6 | 建議內容重複 |
| QC7 | 輸入資料不完整，推論卻標示高信心 |
| QC8 | 只有一個來源的企業關係判斷標示高信心 |
| QC9 | 建議只依據「未知」結論 |
