# 資料工程模組架構

> Issue：P1-DATA-02（#11）｜負責人：data｜路徑歸屬：`docs/data-platform/`（data）
> 本文件依據 `CLAUDE.md`、`docs/ExhibitIQ_專案總規範.md`、`docs/architecture/module-boundaries.md`、`docs/specs/data-package-contract.md`。與它們衝突時，以它們為準。
> 「已建立」＝此 Issue 已存在於 repo；「規劃中」＝尚未建立，名稱與位置待對應 Issue 決定。

## 1. 模組責任

| 路徑 | 責任 | 不做 | 狀態 |
|---|---|---|---|
| `crawler/` | 取得來源（HTML、PDF、CSV、Excel、人工輸入），保存為不可變的原始證據，並記錄來源 ID、取得時間、內容雜湊 | 清洗、去重、打包、AI 分析 | 套件已建立；已有來源設定、錯誤格式、執行日誌（D1-07，見 `run-logging-and-errors.md`），無爬取邏輯 |
| `etl/` | 可重現的清洗、標準化、企業去重、品質與完整度檢查、資料包寫出，以及**唯一一份**資料包驗證程式 | 爬取來源、AI 推論 | 套件已建立；已有資料包讀寫工具（D1-04，見 `package-io.md`），驗證程式（D1-05）尚未建立 |
| `.github/workflows/` | 在雲端執行驗證、擷取、ETL（不直接寫入 `main`） | — | 規劃中（D1-02、D1-08） |
| `data/` | 資料產物：`raw/`、`normalized/`、`packages/`、`history/` | 原始資料不可修改 | 規劃中（Phase 2 起使用） |
| `tests/data/` | 資料工程測試 | — | 已建立 |
| `schemas/` | **唯一資料契約**，由專案負責人維護，資料工程只讀 | 資料工程不得修改 | 已同步（`1.0.0-draft.1`） |

## 2. 資料流

```text
來源（官網、檔案、人工輸入）
   │  crawler/
   ▼
原始快照 + source 紀錄（source_id、retrieved_at、content_sha256）   ← 不可變
   │  etl/
   ▼
標準化資料 → 去重（company_id 穩定）→ 品質／完整度檢查
   │  etl/
   ▼
資料包 data/packages/<exhibition_id>/<edition_year>/<dataset_id>/   ← 8 個檔案、不可修改
   │  etl/ 驗證程式（R1–R11）
   ▼
AI Skill 讀取（專案負責人的範圍；資料包是兩邊的介面）
```

資料包目錄組成、序列化、雜湊與驗證規則見 `docs/specs/data-package-contract.md` §3、§5、§6、§12。

## 3. 不變條件

1. 原始證據不可變；AI 推論不得寫回來源事實。核心資料不得出現 `ai_inferred`。
2. 不虛構筆數、企業資料、來源或信心值。官方筆數沒有來源就是 `null`。
3. `schemas/` 以外不得有任何 Schema 或欄位清單。`tests/data/test_skeleton.py` 會檢查是否有 `*.schema.json` 出現在 `schemas/` 以外。
4. 驗證程式只有一份，位於 `etl/`，從本機 `schemas/v1/` 載入，不透過網路。
5. 要改共用 Schema，依 `schemas/VERSIONING.md` §5 開 `[schema]` Issue，等專案負責人核准；不得在 `dev/data-platform` 直接修改 `schemas/`。
6. 一個工作項目只動它授權的路徑；不碰 `main`、不碰 `dev/ai-intelligence`。

## 4. 規劃中的擴充

工作項目編號以 `docs/DEVELOPMENT_PLAN.md` 為準；下表只說明預期內容與位置，細節由各工作項目決定。

| 工作項目 | 預期內容 | 預期位置 |
|---|---|---|
| D1-04 | JSONL、manifest、來源索引的讀寫工具（依契約 §5、§6 的序列化與雜湊）（**已完成**） | `etl/` |
| D1-05 | Schema 載入與資料包驗證程式（R1–R11）、完整性測試；以 `schemas/v1/examples/package/` 為正向測試向量 | `etl/`、`tests/data/` |
| D1-06 | 兩組不同結構的合成展覽測試資料（`data_origin: "synthetic"`） | `data/samples/<exhibition_id>/` |
| D1-11 | 通用的新展覽來源評估流程與範本（以 D1-10 MSPO 評估為第一個實例） | `docs/data-platform/` |
| D1-07 | 來源設定、執行日誌與錯誤格式（**已完成**） | `crawler/` |
| Phase 2 | 共用爬蟲框架與來源註冊機制（D2-01）、測試展覽的來源適配器與匯入轉換（展覽差異只放在來源設定、適配器或對應設定）、去重與別名、完整度報告、資料包發布、新增展覽 workflow（D2-13） | `crawler/`、`etl/`、`data/`、`.github/workflows/` |

## 5. 本骨架刻意不包含的東西

- 沒有爬蟲、來源註冊機制、基底類別或抽象介面：Phase 2 才有實際來源可以驗證設計，現在先定介面容易定錯。
- 沒有 `data/` 目錄：資料產物從 Phase 2 才會出現。
- 沒有 Schema、欄位清單或驗證邏輯。
