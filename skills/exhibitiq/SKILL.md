---
name: exhibitiq
description: ExhibitIQ exhibition intelligence analysis. Use when asked to analyse an exhibition's exhibitors, rank opportunities, classify companies (customer / competitor / partner), recommend BXR products or produce an exhibition intelligence report from an ExhibitIQ data package. Produces a schema-valid analysis_result JSON plus a Markdown report, with every claim grounded in package sources.
---

# ExhibitIQ Skill（A2-01 入口規格）

> 負責人：Eric（`ai`）。契約：`schemas/v1/analysis_result.schema.json`、`docs/specs/analysis-result-contract.md`。
> 本 Skill 適用於**任何展覽**；不得假設、優先或寫死特定展覽（`CLAUDE.md` V2.3 強制規則）。

## 1. 什麼時候使用
使用者要求分析某個展覽或屆次的參展商、商機排序、企業關係分類、BXR 產品建議、參展決策，或要產生展會情報報告時。

## 2. 輸入（只讀這些檔案）
| 輸入 | 位置 | 規則 |
|---|---|---|
| 資料集索引 | `data/index/datasets.json`（尚未產生時用 `schemas/v1/examples/index/dataset_index.example.json`） | 只分析 `latest_dataset_id`，也就是驗證通過的資料包 |
| 資料包 | 索引中 `location` 指向的目錄 | 分析前**必須**先執行 `python -m etl.validate <dir>`（data 的驗證程式），不通過就停止並回報 |
| BXR 產品卡、分類 | `knowledge/bxr-products/`、`knowledge/taxonomy/` | 只能使用 `approval_status: approved` 的內容；沒有核定的產品卡時，**不得提出產品建議** |
| 展覽登錄 | `data/registry/<exhibition_id>/registration.json` | 只作為背景；登錄資料不是來源事實 |

## 3. 輸出
1. **分析結果 JSON：** `reports/analysis/<input_dataset_id>/<analysis_id>.json`，必須通過 `analysis_result.schema.json` 與規則 AR1～AR10。`review_status` 一律從 `draft` 開始。
2. **Markdown 報告：** 同一目錄下的 `<analysis_id>.md`，**只能由分析結果 JSON 產生**，不得加入 JSON 裡沒有的結論（`references/report-spec.md`）。Dashboard 與 PDF 也使用同一份 JSON。

## 4. 工作流程

輔助程式：`python skills/exhibitiq/scripts/exhibitiq_tools.py`，子命令 `list`、`select`、`validate-package`、`classify`、`score`、`relate`（關係候選，規則見 `references/relationship-rules.md`）、`validate-analysis`、`save-analysis`、`report`（用法見 `README.md`）。
1. 讀取資料集索引，選定展覽與屆次，取得最新資料包路徑。
2. 執行 `python -m etl.validate <package_dir>`；失敗就停止並回報錯誤，不分析。
3. 讀取 `manifest.json`；記下 `dataset_id`、`content_hash`、`data_origin`、`completeness_status`。合成資料的分析結果必須標 `data_origin: synthetic`。
4. 依 `references/evidence-rules.md` 產生結論、不確定性、評分、關係分類與建議，每一項都要引用資料包中的 `source_id`。
5. 驗證分析結果（目前是 `tests/contract/analysis_check.py` 與 `knowledge_check.check_analysis_products`；A2-11 會提供正式的驗證程式）。不通過就修正，**不得發布**。
6. 從 JSON 產生 Markdown 報告。
7. 回報：分析檔路徑、驗證結果、主要不確定性與資料完整度。

## 5. 絕對禁止
- 虛構企業、展位、數量、技術能力、報價、趨勢、引文或信心數字。
- 把 AI 推論寫成 `fact`，或寫回資料包。
- 引用未核定的 BXR 產品，或自行推測產品規格。
- 用估計值補足官方筆數；完整度不是 `complete` 時，必須在報告中說明影響。

## 6. 參考文件
- `references/evidence-rules.md`：結論類型、證據、不確定性、評分的判斷規則。
- `references/report-spec.md`：報告類型、必要章節與驗收清單。
