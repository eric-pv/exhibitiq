# ExhibitIQ Schema 版本政策

> 狀態：Phase 1 核定版（P1-AI-03，Issue #3）
> 負責人：專案負責人（`ai`）。目錄負責人規則見 [`docs/architecture/module-boundaries.md`](../docs/architecture/module-boundaries.md)。

## 1. 適用範圍

本政策適用於 `schemas/` 內所有資料契約：展覽、屆次、企業、參展紀錄、來源、擷取批次、資料包 manifest、變更紀錄、AI 分析結果與證據引用、BXR 產品知識。`schemas/` 是**唯一**資料契約來源（總規範 §6）；任何模組都不得在其他位置另行定義欄位清單。

## 2. 格式與檔案配置

- 所有 Schema 使用 **JSON Schema Draft 2020-12**。每個檔案的 `$schema` 必須是 `https://json-schema.org/draft/2020-12/schema`。
- 每個 MAJOR 版本一個目錄：`schemas/v<MAJOR>/`。
- 檔名：`<entity>.schema.json`，`entity` 使用小寫 snake_case（例如 `crawl_run.schema.json`）。
- `$id`：`https://exhibitiq.invalid/schemas/v<MAJOR>/<entity>.schema.json`。
  - `.invalid` 是保留網域，保證不會解析到任何網站；`$id` 只是識別碼。
  - 驗證程式**必須從本機 `schemas/` 載入**所有 Schema 並在本機解析 `$ref`，不得透過網路取得。
- 同一 MAJOR 目錄內的檔案以相對路徑互相 `$ref`（例如 `"$ref": "source.schema.json"`）。
- 每個 MAJOR 目錄有一個 `VERSION` 檔，內容只有一行完整版本號（例如 `1.0.0`）。實際檔案由 P1-AI-04 建立。

## 3. 版本號

- 採用 [Semantic Versioning 2.0.0](https://semver.org/)：`MAJOR.MINOR.PATCH`。
- **整組 Schema 共用一個版本號**，不各檔分開編號；任一檔案變更，整組版本隨之提升。
- 資料必須宣告自己符合的版本：
  - `manifest.json` 與 AI 分析結果**必須**有 `schema_version` 欄位（總規範 §6）。
  - JSONL 紀錄是否逐筆攜帶 `schema_version`，由 P1-AI-04 決定並寫入 Schema。

### 3.1 Phase 1 草案期

- P1-AI-04 首次發布為 `1.0.0-draft.1`，放在 `schemas/v1/`。
- 草案期間（`1.0.0-draft.N`）**任何變更都可能不相容**；每次變更將 `N` 加 1，並記錄於 [`CHANGELOG.md`](CHANGELOG.md)。
- 草案期間，驗證程式要求資料的 `schema_version` 與 `VERSION` **完全相同**。
- Phase 1 階段整合經專案負責人驗收通過時，定版為 `1.0.0`。之後適用第 4 節規則。

## 4. 相容性政策（定版後）

### 4.1 核心保證

**同一 MAJOR 內向後相容：** 任何符合 `X.m.p` 的資料，必須仍然通過 `X.n.q`（`n ≥ m`）的驗證。

### 4.2 驗證程式的判斷規則

| 資料宣告的 `schema_version` | 驗證程式載入的版本 | 結果 |
|---|---|---|
| MAJOR 不同 | — | **拒絕**，錯誤訊息指出 MAJOR 不符 |
| 同 MAJOR，MINOR ≤ 目前版本 | 目前版本 | 正常驗證 |
| 同 MAJOR，MINOR > 目前版本 | — | **拒絕**，錯誤訊息指出驗證程式的 Schema 版本過舊 |
| 草案版（含 `-draft.N`） | 草案版 | 必須完全相同（3.1） |

### 4.3 變更分類

| 變更 | 版本提升 |
|---|---|
| 刪除或改名欄位 | **MAJOR** |
| 變更欄位型別或語意 | **MAJOR** |
| 新增必填欄位 | **MAJOR** |
| 刪除 enum 值 | **MAJOR** |
| 收緊限制（例如 `pattern`、`maxLength`、`minimum`） | **MAJOR** |
| 變更 ID 格式或 `content_hash` 計算方式 | **MAJOR** |
| 新增選填欄位 | MINOR |
| 新增 enum 值 | MINOR |
| 新增 Schema 檔（新實體） | MINOR |
| 放寬限制 | MINOR |
| 只修改 `description`、`title`、`examples` 或文件，驗證結果不變 | PATCH |

判斷不確定時，以較高等級處理。

### 4.4 物件的額外欄位

- 紀錄型物件預設 `"additionalProperties": false`，以攔截拼字錯誤與未經核准的欄位。
- 需要新欄位時依第 5 節提出變更，不得由生產端自行加入。
- 消費端程式處理 enum 時必須有預設分支，以便 MINOR 新增 enum 值時不會當機。

### 4.5 MAJOR 升級

- 新 MAJOR 建立新目錄（例如 `schemas/v2/`），舊目錄保留到下一次階段整合完成；同時最多存在兩個 MAJOR。
- 必須在 [`CHANGELOG.md`](CHANGELOG.md) 提供遷移說明：哪些欄位改變、舊資料如何重新產生。
- 已發布的原始資料與資料包**不得**改寫成新版本；以重新執行 ETL 產生新的資料包取代（總規範：Raw evidence 不可變更）。
- 階段進行中，另一方已經依賴的契約應避免 MAJOR 變更；確有必要時由專案負責人決定。

## 5. 變更程序

任何人都可以提出 Schema 變更，但只有專案負責人可以核准與修改 `schemas/`。

1. **提出：** 開 Issue，標題以 `[schema]` 開頭，內容包含：
   - 變更原因與使用情境
   - 影響的 Schema 檔與欄位
   - 建議的版本提升等級（依 4.3）與相容性影響
   - 一筆變更後的範例資料
2. **核准：** 專案負責人在 Issue 中明確留言核准，或說明拒絕原因。未核准不得實作。
3. **實作（`ai`）：** 在 `feature/ai/<issue>-<slug>` 中一次完成：
   - 修改 `schemas/v<MAJOR>/` 內的 Schema 檔
   - 更新 `VERSION`
   - 在 [`CHANGELOG.md`](CHANGELOG.md) 新增紀錄
   - 更新 `data/samples/golden/` 與 `tests/contract/`，並在雲端通過測試
   - PR base=`dev/ai-intelligence`，由專案負責人合併
4. **同步：** 依 [`module-boundaries.md`](../docs/architecture/module-boundaries.md) 第 4 節把 `schemas/` 同步到 `dev/data-platform`，由同事合併同步 PR。
5. **跟進（`data`）：** 同事在自己的功能分支更新驗證程式、生產端程式與 `data/samples/<exhibition_id>/`，PR base=`dev/data-platform`，自行合併。

## 6. 禁止事項

- 在 `schemas/` 以外的位置定義或複製 Schema、欄位清單。
- 在 `dev/data-platform` 上直接修改 `schemas/`（只能透過第 4 節的同步取得）。
- 未經核准修改 Schema，或修改後不更新 `VERSION`、`CHANGELOG.md`、樣本與測試。
- 驗證程式透過網路取得 Schema。
- 為了配合新版 Schema 而改寫已發布的原始資料。
