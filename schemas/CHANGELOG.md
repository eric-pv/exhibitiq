# Schema 變更紀錄

格式依 [`VERSIONING.md`](VERSIONING.md)。每筆紀錄包含：版本、日期、Issue／PR、變更類別（MAJOR／MINOR／PATCH／draft）、變更內容、相容性與遷移說明。最新的放最上面。

## 1.0.0-draft.1 — 2026-11-03

- Issue：#7（P1-AI-04）
- 類別：draft（首次發布）
- 內容：新增 `schemas/v1/` 核心資料契約：`common`、`exhibition`、`edition`、`company`、`participation`、`source`、`crawl_run`、`manifest`、`change`；新增合成範例資料包 `examples/package/` 與 `examples/change.example.json`。規格見 [`docs/specs/data-package-contract.md`](../docs/specs/data-package-contract.md)。
- 相容性：首次發布，無既有資料。
