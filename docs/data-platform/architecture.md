# 資料工程模組架構

> Issue：P1-DATA-02（#11）｜負責人：data｜路徑歸屬：`docs/data-platform/`（data）
> 本文件依據 `CLAUDE.md`、`docs/ExhibitIQ_專案總規範.md`、`docs/architecture/module-boundaries.md`、`docs/specs/data-package-contract.md`。與它們衝突時，以它們為準。
> 「已建立」＝此 Issue 已存在於 repo；「規劃中」＝尚未建立，名稱與位置待對應 Issue 決定。

## 1. 模組責任

| 路徑 | 責任 | 不做 | 狀態 |
|---|---|---|---|
| `crawler/` | 取得來源（HTML、PDF、CSV、Excel、人工輸入），保存為不可變的原始證據，並記錄來源 ID、取得時間、內容雜湊 | 清洗、去重、打包、AI 分析 | 套件已建立；已有來源設定、錯誤格式、執行日誌（D1-07，見 `run-logging-and-errors.md`），以及共用爬蟲框架（D2-01，見 `crawler-framework.md`）；尚無內建適配器 |
| `etl/` | 可重現的清洗、標準化、企業去重、品質與完整度檢查、資料包寫出，以及**唯一一份**資料包驗證程式 | 爬取來源、AI 推論 | 套件已建立；已有資料包讀寫工具（D1-04，見 `package-io.md`）與唯一的資料包驗證程式（D1-05，見 `package-validator.md`） |
| `.github/workflows/` | 在雲端執行驗證、擷取、ETL（不直接寫入 `main`） | — | 規劃中（D1-02、D1-08） |
| `data/` | 資料產物：`raw/`、`normalized/`、`packages/`、`history/` | 原始資料不可修改 | 已有 `data/samples/`（合成測試資料，D1-06，見 `synthetic-samples.md`）；`raw/`、`normalized/`、`packages/`、`history/` 從 Phase 2 起使用 |
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
| D1-05 | Schema 載入與資料包驗證程式（R1–R11）、完整性測試；以 `schemas/v1/examples/package/` 為正向測試向量（**已完成**） | `etl/`、`tests/data/` |
| D1-06 | 兩組不同結構的合成展覽測試資料（`data_origin: "synthetic"`）（**已完成**） | `data/samples/<exhibition_id>/` |
| D1-07 | 來源設定、執行日誌與錯誤格式（**已完成**） | `crawler/` |
| D2-01 | 共用爬蟲框架與來源註冊機制（**已完成**，見 `crawler-framework.md`） | `crawler/`、`etl/ids.py` |
| D2-04 | HTML／PDF／CSV／Excel 匯入轉換與欄位對應設定（**已完成**，見 `file-import.md`） | `crawler/importers.py`、`crawler/file_import.py` |
| D2-06 | 來源快照、擷取批次與錯誤紀錄的保存（**已完成**，見 `snapshot-storage.md`） | `crawler/store.py` |
| D2-07 | 清洗、標準化、企業去重與別名關聯、穩定 company_id（**已完成**，見 `normalize-and-dedupe.md`） | `etl/normalize.py`、`etl/registry.py`、`etl/build_records.py` |
| D2-08 | 跨展會／跨年度參展歷史與變更比對、同一屆再次取得的攜帶下架紀錄（**已完成**，見 `changes-and-history.md`） | `etl/changes.py`、`etl/history.py` |
| D2-09 | 完整度、缺漏與品質報告（**已完成**，見 `completeness-report.md`） | `etl/report.py` |
| D2-10 | 不刪除原始資料的初步規則篩選（**已完成**，見 `screening.md`） | `etl/screening.py` |
| D2-12 | 資料集索引與管線狀態 `data/index/datasets.json`（Dashboard 讀取；含取得失敗與驗證失敗紀錄；IR1–IR7）（**已完成**，見 `dataset-index.md`） | `etl/dataset_index.py`、`etl/build_index.py` |
| D3-04 | 跨資料包企業搜尋、同一屆所有資料包的時間軸（`previous_dataset_id` 鏈檢查）、任兩個資料包的差異輸出（**已完成**，見 `catalog.md`） | `etl/catalog.py` |
| D3-08 | 資料工程模組回歸測試：整條流程輸出的基準檔、模組測試覆蓋與命令列檢查（**已完成**，見 `regression-tests.md`） | `tests/data/regression_outputs.py`、`tests/data/regression/` |
| D4-03 | 快照驗證、資料包逐位元組重新產生檢查、可重現且可驗證的備份與還原（**已完成**，見 `integrity-and-backup.md`） | `etl/integrity.py` |
| D4-07 | 資料品質關卡（Q1–Q5：失敗／空名單／大幅縮水阻擋）與 13 種來源失效端到端測試（**已完成**，見 `quality-and-source-failures.md`） | `etl/quality.py`、`tests/data/test_quality_and_failures.py` |
| D4-06 | 爬蟲與資料格式維護手冊：文件索引、格式速查、新增來源與失效處理、Schema 升版、備份；由測試確認提到的檔案與指令存在（**已完成**，見 `maintenance.md`） | `docs/data-platform/maintenance.md`、`tests/data/test_maintenance_docs.py` |
| D2-02 | 第一份真實資料（IACP 2026，人工列印 PDF 匯入，662／662）；通用的檔案匯入命令列與 `printed-listing` 適配器（**已完成檔案匯入部分**，見 `import-file.md`；網站自動擷取對此來源不可行） | `etl/import_file.py`、`crawler/printed_listing.py`、`data/sources/` |
| D2-11 | 組裝含 manifest 與來源索引的資料包，通過驗證程式才發布（**已完成**，見 `assemble-package.md`） | `etl/assemble.py` |
| D1-11 | 通用的展覽來源探索與可行性評估流程與範本（**已完成**，見 `source-assessment-process.md`、`source-assessment-template.md`） | `docs/data-platform/` |
| Phase 2 | 共用爬蟲框架與來源註冊機制（D2-01）、測試展覽的來源適配器與匯入轉換（展覽差異只放在來源設定、適配器或對應設定）、去重與別名、完整度報告、資料包發布、新增展覽 workflow（D2-13） | `crawler/`、`etl/`、`data/`、`.github/workflows/` |

## 5. 本骨架刻意不包含的東西

- 沒有爬蟲、來源註冊機制、基底類別或抽象介面：Phase 2 才有實際來源可以驗證設計，現在先定介面容易定錯。
- 沒有真實資料：`data/` 目前只有合成測試資料；真實資料產物從 Phase 2 才會出現。
- 沒有 Schema、欄位清單或驗證邏輯。
