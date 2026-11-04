# ExhibitIQ 分析結果契約 v1

> 狀態：`1.0.0-draft.5`（Phase 1 草案期，依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) §3.1）
> 負責人：專案負責人（`ai`）。工作項目 A1-06。
> 機器可讀契約：[`schemas/v1/analysis_result.schema.json`](../../schemas/v1/analysis_result.schema.json)。本文件與 Schema 衝突時，以 Schema 為準，並視為需要修正的錯誤。
> 輸入資料包的格式見 [`data-package-contract.md`](data-package-contract.md)。

## 1. 用途

一份分析結果是**一次 AI 分析的完整產出**，也是 Dashboard、Markdown 報告與 PDF 的**唯一內容來源**。網頁和 PDF 不得各自產生不同的結論。

產生者：ExhibitIQ Skill（`skills/exhibitiq/`）。讀取者：Dashboard（`site/`）、報告產生程式。

## 2. 存放位置

```text
reports/analysis/<input_dataset_id>/<analysis_id>.json
```

- 一份 JSON 檔一次分析；產生後不修改。重新分析就產生新的 `analysis_id`。
- 人工審核只能改 `review_status`、`reviewed_by`、`reviewed_at`，並以新的 commit 記錄。

## 3. 頂層欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `schema_version` | ✅ | 草案期必須等於 `schemas/v1/VERSION` |
| `analysis_id` | ✅ | `ana_` + ULID |
| `analysis_type` | ✅ | `exhibition_overview`、`company_intelligence`、`opportunity_ranking`、`competitive_landscape`、`partner_channel`、`market_trend`、`product_recommendation`、`exhibition_strategy`、`cross_exhibition_comparison` |
| `title`、`summary` | `title` ✅ | |
| `input_dataset_id`、`input_hash` | ✅ | 輸入資料包的 `dataset_id` 與 manifest 的 `content_hash` |
| `additional_inputs` | | 跨展會或跨年度比較時的其他資料包（`dataset_id`、`content_hash`） |
| `knowledge_version` | | 使用的 BXR 產品知識庫版本（A1-09） |
| `data_origin` | ✅ | 輸入是合成資料時必須是 `synthetic` |
| `skill_version` | ✅ | |
| `model` | | `provider`、`name`、`version`（取得得到時填寫） |
| `generated_at` | ✅ | UTC |
| `review_status` | ✅ | `draft`（未審核）、`human_reviewed`、`approved`、`rejected`；非 `draft` 時必須有 `reviewed_by`、`reviewed_at` |
| `evidence_source_ids` | ✅ | 所有子項目引用的來源 ID 聯集 |
| `conclusions` | ✅ | 結論（第 4 節） |
| `uncertainties` | ✅ | 不確定性（第 5 節） |
| `scores` | | 評分（第 6 節） |
| `relationships` | | 企業關係分類（第 7 節） |
| `recommendations` | ✅ | 建議（第 7 節） |

文件內的子項目使用**區域 ID**：`cl-…`（結論）、`un-…`（不確定性）、`sc-…`（評分）、`rel-…`（關係）、`rec-…`（建議），在同一份文件中不得重複。

## 4. 結論與結論類型

每一條結論都必須標明 `claim_type`，Dashboard 依此顯示 `ClaimBadge`：

| `claim_type` | 意義 | 必填 | 禁止 |
|---|---|---|---|
| `fact` | 引用資料包中的來源事實 | `evidence_source_ids`（≥1）、`verification_status`（`verified`、`unverified`、`human_confirmed`） | `insufficient_data`、`ai_inferred` |
| `inference` | AI 推論 | `evidence_source_ids`（≥1）、`confidence`、`rationale`、`uncertainty_ids`（≥1） | 數字信心值 |
| `unknown` | 資料不足，無法判斷 | `missing_data`（說明缺什麼） | `confidence` |

- **推論一定要有依據**：沒有來源的推論不能寫成結論。
- `confidence` 只能是 `low`、`medium`、`high`，**不使用百分比**，避免產生沒有依據的精確度。
- `subjects` 標示結論涉及的展覽、屆次、企業或參展紀錄。

## 5. 不確定性

`uncertainty_id`、`description`、`impact`（`low`、`medium`、`high`）。推論、關係分類與建議以 `uncertainty_ids` 引用。資料包完整度不是 `complete` 時，應該列出一條不確定性說明影響。

## 6. 評分（可拆解）

```text
score: score_id、score_model_id（例如 opportunity@1）、subject、total_points、max_total_points、rank、factors[]
factor: factor_id、label、status、points、max_points、evidence_source_ids、claim_ids、rationale
```

- `status: "scored"`：必須有 `evidence_source_ids`（≥1）。
- `status: "insufficient_data"`：**`points` 必須是 0**。沒有證據的因子不計分，也不推估。
- `total_points` = 各因子 `points` 加總；`max_total_points` = 各因子 `max_points` 加總。
- 同一個 `score_model_id` 的所有評分使用相同的因子組合；`rank` 從 1 開始連續編號，並依 `total_points` 由高到低排列。
- Dashboard 的 `ScoreBreakdown` 直接顯示每個因子、分數、依據與來源。

## 7. 關係分類與建議

**關係分類（`relationships`）**：`potential_customer`、`competitor`、`partner`、`channel`、`unrelated`、`unknown`。關係分類**一律是 AI 推論**，必須有 `rationale`、`confidence`、`evidence_source_ids`（≥1）、`uncertainty_ids`（≥1）。

**建議（`recommendations`）**：
- 類型：`visit_priority`、`exhibit_product`、`participation_decision`、`partnership`、`market_entry`、`other`；優先度 `high`、`medium`、`low`。
- 必須有 `rationale`、`based_on_claim_ids`（≥1）、`evidence_source_ids`（≥1）；不能只根據 `unknown` 結論提出建議。
- `assumptions` 列出前提（例如預算假設）。
- `product_ids` 只能引用**經專案負責人核准**的 BXR 產品（格式 `bxr-…`，產品卡屬於 A1-09）。

## 8. 驗證規則

規則編號與 `tests/contract/analysis_check.py` 相同。

| 編號 | 規則 |
|---|---|
| AR1 | 通過 `analysis_result.schema.json`（第 4～7 節的必填與禁止條件由 Schema 強制） |
| AR2 | `schema_version` 與 `VERSION` 相同 |
| AR3 | 區域 ID 不重複 |
| AR4 | 所有 `uncertainty_ids`、`claim_ids`、`based_on_claim_ids`、`score_ids` 都存在；建議不能只根據 `unknown` 結論 |
| AR5 | 頂層 `evidence_source_ids` 等於所有子項目引用來源的聯集 |
| AR6 | 評分加總、因子組合一致、排名連續且依分數排序 |
| AR7 | `input_dataset_id`、`input_hash` 與輸入資料包的 manifest 相同 |
| AR8 | 所有引用的來源都在輸入資料包的 `sources.jsonl`；所有 `subjects` 與評分、關係的企業都存在於資料包 |
| AR9 | 輸入是合成資料時，`data_origin` 必須是 `synthetic` |
| AR10 | 建議的 `product_ids` 只能引用已核定的 BXR 產品卡（[`knowledge-base-contract.md`](knowledge-base-contract.md) §5；`tests/contract/knowledge_check.py`） |

**驗證失敗的分析結果不能發布到 Dashboard 或報告。** 正式的分析驗證程式屬於 A2-11（`skills/exhibitiq/`）；`tests/contract/analysis_check.py` 只是用來證明範例符合契約的參考檢查。

## 9. 範例

[`schemas/v1/examples/analysis/analysis_result.example.json`](../../schemas/v1/examples/analysis/analysis_result.example.json)：以 [`examples/package/`](../../schemas/v1/examples/package/) 為輸入的**合成**商機排序分析，通過 AR1–AR9。包含三種結論類型、兩種因子狀態、一條關係分類、一條拜訪建議；沒有引用任何 BXR 產品（產品知識庫尚未建立）。

## 10. 已知限制

- 草案期間欄位可能調整。
- 產品卡格式、分類架構屬於 A1-09；本契約只定義產品 ID 格式。
- 評分模型（各因子的定義與配分）屬於 A2-07；本契約只定義評分的結構與算術規則。
