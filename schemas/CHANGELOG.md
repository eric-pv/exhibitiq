# Schema 變更紀錄

格式依 [`VERSIONING.md`](VERSIONING.md)。每筆紀錄包含：版本、日期、Issue／PR、變更類別（MAJOR／MINOR／PATCH／draft）、變更內容、相容性與遷移說明。最新的放最上面。

## 1.0.0-draft.6 — 2026-11-04

- 工作項目：A2-15（Eric 2026-11-04 核准）
- 類別：draft（只新增，相容）
- 內容：新增 `analysis_profile.schema.json`（分析設定檔：模式、關鍵字、企業關係訊號、評分權重）；`common.schema.json` 新增 `analysis_profile_id`、`analysis_mode`、`keyword`；`analysis_result` 新增選填 `analysis_config`（規則 AR11）；新增 `examples/profile/` 與 `examples/analysis/analysis_result.with_config.example.json`。規格見 [`docs/specs/analysis-profile-contract.md`](../docs/specs/analysis-profile-contract.md)。
- 相容性：**草案期例外：舊資料不需改寫。** 新增 [`v1/COMPATIBILITY.json`](v1/COMPATIBILITY.json)，驗證程式接受 `1.0.0-draft.5` 與 `1.0.0-draft.6`；新產生的資料寫 `1.0.0-draft.6`。資料工程的驗證程式若比對 `VERSION` 完全相同，同步後請改為讀取 `COMPATIBILITY.json` 的 `accepted`。

## 1.0.0-draft.5 — 2026-11-04

- 工作項目：A1-10
- 類別：draft
- 內容：新增 `exhibition_registration.schema.json`（展覽名冊：`data/registry/<exhibition_id>/registration.json`）與 `examples/registry/`。規格見 [`docs/specs/exhibition-registry-contract.md`](../docs/specs/exhibition-registry-contract.md)。
- 相容性：既有欄位沒有改變；**只有版本號改變**。資料包、資料集索引、分析結果與知識庫檔案的 `schema_version` 必須改成 `1.0.0-draft.5`。

## 1.0.0-draft.4 — 2026-11-04

- 工作項目：A1-09
- 類別：draft
- 內容：新增 `bxr_product.schema.json`（產品卡；規格必須指向依據文件；核定狀態）與 `taxonomy.schema.json`（六個分析分類面向）；新增 `examples/knowledge/`。規格見 [`docs/specs/knowledge-base-contract.md`](../docs/specs/knowledge-base-contract.md)。分析結果新增規則 AR10：建議只能引用已核定的產品卡。
- 相容性：既有欄位沒有改變；**只有版本號改變**。資料包 manifest、分析結果與資料集索引的 `schema_version` 必須改成 `1.0.0-draft.4`。

## 1.0.0-draft.3 — 2026-11-03

- 工作項目：A1-07
- 類別：draft
- 內容：新增 `dataset_index.schema.json`（已登錄展覽、資料取得方式與來源評估、各屆次最近一次取得結果〔含失敗〕、資料包摘要與驗證狀態、系統通知）；新增 `examples/index/dataset_index.example.json`。規格見 [`docs/specs/dataset-index-contract.md`](../docs/specs/dataset-index-contract.md)。
- 相容性：既有欄位沒有改變；**只有版本號改變**。資料包 manifest 與分析結果的 `schema_version` 必須改成 `1.0.0-draft.3`。

## 1.0.0-draft.2 — 2026-11-03

- 工作項目：A1-06
- 類別：draft
- 內容：新增 `analysis_result.schema.json`（結論類型 fact／inference／unknown、不確定性、可拆解評分、企業關係分類、建議）；`common.schema.json` 新增 `bxr_product_id`；新增 `examples/analysis/analysis_result.example.json`。規格見 [`docs/specs/analysis-result-contract.md`](../docs/specs/analysis-result-contract.md)。
- 相容性：核心資料欄位沒有改變；**只有版本號改變**。依草案期規則，資料包 manifest 的 `schema_version` 必須改成 `1.0.0-draft.2`（`manifest.json` 不參與 `content_hash`，範例資料包的雜湊不變）。

## 1.0.0-draft.1 — 2026-11-03

- Issue：#7（P1-AI-04）
- 類別：draft（首次發布）
- 內容：新增 `schemas/v1/` 核心資料契約：`common`、`exhibition`、`edition`、`company`、`participation`、`source`、`crawl_run`、`manifest`、`change`；新增合成範例資料包 `examples/package/` 與 `examples/change.example.json`。規格見 [`docs/specs/data-package-contract.md`](../docs/specs/data-package-contract.md)。
- 相容性：首次發布，無既有資料。
