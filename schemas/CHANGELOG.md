# Schema 變更紀錄

格式依 [`VERSIONING.md`](VERSIONING.md)。每筆紀錄包含：版本、日期、Issue／PR、變更類別（MAJOR／MINOR／PATCH／draft）、變更內容、相容性與遷移說明。最新的放最上面。

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
