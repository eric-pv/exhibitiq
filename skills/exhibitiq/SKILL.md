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
| 分析設定檔（主題） | `knowledge/analysis-profiles/<profile_id>.json`（**已提交**的版本；本機草稿不存在雲端） | 決定模式、關鍵字、關係訊號、評分權重；使用者沒指定時先問要用哪個主題，或用 `default-library` |
| BXR 產品卡 | `knowledge/bxr-products/` | **只有 A 模式使用。** 目前全部是 `draft`：可以用於辨識候選，但報告必須提示「產品資料未核定」；**產品建議（`product_ids`）只能引用 `approved` 的產品卡**（AR10） |
| 展覽登錄 | `data/registry/<exhibition_id>/registration.json` | 只作為背景；登錄資料不是來源事實 |

## 3. 輸出
1. **分析結果 JSON：** `reports/analysis/<input_dataset_id>/<analysis_id>.json`，必須通過 `analysis_result.schema.json` 與規則 AR1～AR11（EV1～EV7），並包含 `analysis_config`（`exhibitiq_tools.py config <profile>` 產生）。`review_status` 一律從 `draft` 開始。
2. **Markdown 報告：** 同一目錄下的 `<analysis_id>.md`，**只能由分析結果 JSON 產生**，不得加入 JSON 裡沒有的結論（`references/report-spec.md`）。Dashboard 與 PDF 也使用同一份 JSON。

## 4. 工作流程

輔助程式：`python skills/exhibitiq/scripts/exhibitiq_tools.py`，子命令 `list`、`select`、`validate-package`、`classify`／`score`／`relate`（都可加 `--profile <分析設定檔>`；關係為多標籤候選，見 `references/relationship-rules.md`）、`config <profile>`（產生分析結果的 `analysis_config`）、`compare <package_dir>... --profile`（跨展覽／跨年度比較與關鍵字趨勢）、`trend <exhibition_id> --profile`（同一展覽的歷史趨勢：各年度家數、關鍵字、再次參展／新參展／未再參展；資料不完整時不判斷新增與流失，只有一個年度時回報資料不足）、`value <package_dir> --profile`（展覽商務價值與拜訪候選，不含預算）、`validate-analysis`、`save-analysis`、`report`（用法見 `README.md`）。
1. 讀取資料集索引，選定展覽與屆次，取得最新資料包路徑。
2. 執行 `python -m etl.validate <package_dir>`（尚未整合時用 `exhibitiq_tools.py validate-package`）；失敗就停止並回報錯誤，不分析。
3. 讀取 `manifest.json`；記下 `dataset_id`、`content_hash`、`data_origin`、`completeness_status`。合成資料的分析結果必須標 `data_origin: synthetic`。
4. **選定分析設定檔**，執行 `config <profile>` 取得 `analysis_config`，再依模式執行：

   | 模式 | 步驟 | 不得 |
   |---|---|---|
   | **A. BXR 商機分析**（`bxr_opportunity`） | `classify`／`relate`／`score --profile` → 閱讀來源確認候選 → 結論、多標籤關係、評分（設定檔有評分模型時）、拜訪與參展建議 | 產品卡未核定時省略提示；推薦未核定產品 |
   | **B. 產業與技術研究**（`industry_research`） | `classify`／`relate --profile` → 依主題整理企業、產品、技術、產業趨勢；結論與不確定性為主 | 讀取或引用 BXR 產品卡；沒有評分模型時評分 |
   | **C. 競爭對手研究**（`competitor_research`） | 以 `targets`（指定企業、技術或產品領域）為中心，`relate --profile` 找出競爭候選 → 技術重疊、產品定位與比較證據 | 依賴 BXR 產品卡；推測對方規格 |

5. 依 `references/evidence-rules.md` 與 `references/relationship-rules.md` 產生結論、不確定性、評分、關係與建議，每一項都要引用資料包中的 `source_id`；關鍵字命中只是候選，確認不了就寫 `unknown`。
6. `validate-analysis`；不通過就修正，**不得發布**。通過後 `save-analysis`（同一展覽可用不同主題或模式重複分析，每次都是新的 `analysis_id`，不覆蓋舊結果）。
7. `report` 產生 Markdown（報告會列出「分析設定」：模式、主題、版本、雜湊、啟用的關鍵字）。
8. 回報：分析檔路徑、使用的主題與版本、驗證結果、主要不確定性與資料完整度。

## 5. 絕對禁止
- 虛構企業、展位、數量、技術能力、報價、趨勢、引文或信心數字。
- 把 AI 推論寫成 `fact`，或寫回資料包。
- 引用未核定的 BXR 產品，或自行推測產品規格。
- 用估計值補足官方筆數；完整度不是 `complete` 時，必須在報告中說明影響。

## 6. 參考文件
- `references/evidence-rules.md`：結論類型、證據、不確定性、評分的判斷規則。
- `references/report-spec.md`：報告類型、必要章節與驗收清單。
