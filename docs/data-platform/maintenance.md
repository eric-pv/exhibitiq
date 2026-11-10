# 爬蟲與資料格式維護手冊

> 工作項目：D4-06｜負責人：data｜適用範圍：`crawler/`、`etl/`、`data/`、`tests/data/`、`docs/data-platform/`
> 給接手維護的人：先讀本文件，再依連結讀各模組文件。本文件只整理已實作並測試過的行為；與 `CLAUDE.md`、`docs/ExhibitIQ_專案總規範.md`、`docs/specs/` 衝突時，以它們為準。`tests/data/test_maintenance_docs.py` 會檢查本文件提到的檔案、模組與文件都存在。

## 1. 文件索引

| 文件 | 內容 | 工作項目 |
|---|---|---|
| [architecture.md](architecture.md) | 模組責任、資料流、不變條件 | P1-DATA-02 |
| [environment.md](environment.md) | 雲端 Python 環境、依賴 | D1-01 |
| [package-io.md](package-io.md) | 資料包讀寫、序列化、雜湊 | D1-04 |
| [package-validator.md](package-validator.md) | 唯一的資料包驗證程式（R1–R11） | D1-05 |
| [synthetic-samples.md](synthetic-samples.md) | 兩組合成測試展覽 | D1-06 |
| [run-logging-and-errors.md](run-logging-and-errors.md) | 來源設定（TOML）、錯誤格式、執行日誌 | D1-07 |
| [source-assessment-process.md](source-assessment-process.md)、[source-assessment-template.md](source-assessment-template.md) | 新展覽的來源評估流程與範本 | D1-11 |
| [mspo-source-assessment.md](mspo-source-assessment.md) | MSPO 來源評估（實例） | D1-10 |
| [crawler-framework.md](crawler-framework.md) | 共用爬蟲框架、適配器、執行狀態 | D2-01 |
| [file-import.md](file-import.md) | CSV／HTML 表格／Excel／PDF 匯入與欄位對應 | D2-04 |
| [snapshot-storage.md](snapshot-storage.md) | 原始快照與擷取批次的保存 | D2-06 |
| [normalize-and-dedupe.md](normalize-and-dedupe.md) | 清洗、標準化、企業去重、穩定 ID | D2-07 |
| [changes-and-history.md](changes-and-history.md) | 再次取得的攜帶、變更紀錄、參展歷史 | D2-08 |
| [completeness-report.md](completeness-report.md) | 完整度與品質報告 | D2-09 |
| [screening.md](screening.md) | 規則篩選（不刪資料） | D2-10 |
| [assemble-package.md](assemble-package.md) | 組裝資料包 | D2-11 |
| [dataset-index.md](dataset-index.md) | 資料集索引 `data/index/datasets.json` | D2-12 |
| [catalog.md](catalog.md) | 搜尋、屆次時間軸、差異 | D3-04 |
| [regression-tests.md](regression-tests.md) | 回歸測試與基準檔 | D3-08 |
| [integrity-and-backup.md](integrity-and-backup.md) | 快照驗證、重新產生、備份與還原 | D4-03 |
| [quality-and-source-failures.md](quality-and-source-failures.md) | 品質關卡、來源失效測試 | D4-07 |
| [import-file.md](import-file.md) | 一個檔案到資料包的命令列、`printed-listing` 與 `pdf-layout-table` 適配器、已提交真實資料的檢查 | D2-02、D2-03 |
| [iacp-2026-source-assessment.md](iacp-2026-source-assessment.md) | IACP 2026 來源評估（第一份真實資料；自動擷取不可行，人工列印 PDF 匯入） | D2-02 |
| [dsa-2026-source-assessment.md](dsa-2026-source-assessment.md) | DSA 2026 來源評估（第二個不同結構：主辦單位 PDF 表格） | D2-03 |
| [maintenance.md](maintenance.md) | 本文件 | D4-06 |

## 2. 資料格式速查

**共用契約只有 `schemas/v1/`**（專案負責人維護；資料端不得修改）。規格文字在 `docs/specs/`：資料包 `data-package-contract.md`、資料集索引 `dataset-index-contract.md`、展覽名冊 `exhibition-registry-contract.md`。版本規則見 `schemas/VERSIONING.md`；目前可接受的版本見 `schemas/v1/COMPATIBILITY.json`。

| 產物 | 位置 | 格式重點 | 誰產生 | 是否契約 |
|---|---|---|---|---|
| 原始證據 | `data/raw/<exhibition_id>/<edition_id>/<crawl_run_id>/` | `snapshots/<source_id>.<ext>`（原樣位元組）、`sources.jsonl`、`crawl_run.json`、`run.log.jsonl`、`errors.json`；不可修改 | `crawler/store.py` | `source`、`crawl_run` 紀錄是 |
| 資料包 | `data/packages/<exhibition_id>/<edition_year>/<dataset_id>/` | 8 個檔案：`manifest.json` ＋ `exhibition.json`、`edition.json`、`companies.jsonl`、`participations.jsonl`、`sources.jsonl`、`crawl_runs.jsonl`、`changes.jsonl`；canonical JSON 一行一筆、依主鍵排序；`content_hash` 不含 manifest；不可修改 | `etl/assemble.py` | 是 |
| 資料集索引 | `data/index/datasets.json` | 每展覽／屆次的資料包摘要、`latest_dataset_id`、`last_acquisition`、通知 | `etl/build_index.py` | 是 |
| 來源評估 | `data/index/assessments.json` | `{exhibition_id: {name, method, status, assessed_at, report_path, notes}}`，人寫 | 人 | 否（索引的輸入） |
| 企業登錄表 | `data/registry/companies.json`（慣例） | 名稱鍵、網站、國家 → `company_id`；`(屆次, company_id)` → `participation_id` | `etl/registry.py` | 否 |
| 參展歷史 | `data/history/companies.json`（慣例） | `company_id` → 各屆參展 | `etl/history.py` | 否 |
| 來源設定與展覽資料 | `data/sources/<exhibition_id>/<edition_id>.toml`、`.info.json` | 適配器與選項；`exhibition`／`edition` 欄位（值須來自匯入的檔案） | 人 | 否 |
| 合成樣本 | `data/samples/` | 由 `data/samples/build_samples.py` 產生，不手改 | 產生程式 | 否（資料端測試資料） |
| 回歸基準 | `tests/data/regression/*.json` | 8 組流程輸出 | `tests/data/regression_outputs.py` | 否 |
| 備份檔 | 由使用者指定（保存位置未決定） | `.tar.gz`＋`backup-manifest.json` | `etl/integrity.py` | 否 |

ID：`src_`、`run_`、`co_`、`pt_`、`chg_` ＋ ULID（`etl/ids.py`）；`dataset_id = <edition_id>.<UTC 時間 YYYYMMDDTHHMMSSZ>`。`company_id` 由登錄表維持跨年度穩定，**登錄表遺失會讓同一企業拿到新 ID**，要與資料包一起保存。

> 路徑注意：`data/registry/` 同時是展覽名冊（A1-10：`data/registry/<exhibition_id>/registration.json`，`docs/architecture/module-boundaries.md` §2 歸 data 寫入）。企業登錄表是該目錄頂層的**檔案**，不是資料夾；2026-11-09 查證 `dev/ai-intelligence` 的 `tests/contract/registry_check.py` 只讀 `*/registration.json`、只對沒有 `registration.json` 的**資料夾**報 RG3，所以不衝突。不要建立名為 `companies.json` 以外的頂層檔案或沒有 `registration.json` 的資料夾。

## 3. 資料流與指令

```text
來源評估（人）→ 來源設定 TOML ＋ 適配器或匯入對應
  → crawler.runner.run_source / crawler.file_import.import_files（sink = crawler.store.RunStore）
  → etl.build_records（企業登錄表）→ etl.changes.carry_forward / diff_records（有前一包時）
  → etl.quality.check_acquisition（阻擋時不發布）→ etl.assemble.assemble_package（內含驗證）
  → etl.build_index → etl.history / etl.report / etl.screening / etl.catalog（讀取）
```

檔案匯入用 `python -m etl.import_file` 一次走完（`import-file.md`）；網站爬取目前以 Python 呼叫；Actions workflow（D2-05、D2-13）為還原狀態（PR #48），恢復與否由 Albert 決定。

| 指令 | 用途 |
|---|---|
| `python -m etl.import_file --config ... --file ... --info ...` | 一個檔案 → 證據 → 紀錄 → 品質關卡 → 資料包 |
| `python -m etl.validate PACKAGE_DIR` | 驗證資料包（R1–R11） |
| `python -m etl.report PACKAGE_DIR [--json]` | 完整度與品質報告 |
| `python -m etl.build_index [--packages data/packages]` | 產生 `data/index/datasets.json` |
| `python -m etl.catalog search\|timeline\|diff ...` | 搜尋企業、屆次時間軸、兩個資料包的差異 |
| `python -m etl.integrity snapshots\|regen\|backup\|verify-backup\|restore ...` | 快照驗證、逐位元組重新產生、備份與還原 |
| `python data/samples/build_samples.py --force` | 重新產生合成樣本 |
| `python -m tests.data.regression_outputs [--write]` | 比對／重寫回歸基準 |
| `python -m pytest -q` | 全部資料端測試（`pyproject.toml` 只收 `tests/data`） |

## 4. 常見維護工作

### 4.1 新增一個展覽來源

1. 依 `source-assessment-process.md` 評估並寫報告；結果寫入 `data/index/assessments.json`。來源有 captcha、登入、403/429 或條款禁止 → **停止並回報**，不繞過。
2. 寫來源設定 TOML（欄位見 `run-logging-and-errors.md` §2）：`name`、`exhibition_id`、`edition_id`、`source_type`（Schema 的 enum）、`start_urls`、`allowed_domains`，選填 `adapter`、`[options]`。設定檔不得含 token／密碼類欄位。
3. 檔案來源（CSV／Excel／HTML 表格／PDF 文字層）：`adapter = "file-import"`，在 `[options.mapping]` 寫欄位對應（`file-import.md` §2）；瀏覽器列印的名單頁用 `adapter = "printed-listing"`（`import-file.md` §2）；主辦單位的 PDF 表格用 `adapter = "pdf-layout-table"`（§3），國家寫法另附 `--country-aliases` 對照表。**不需要寫程式**。設定放 `data/sources/<exhibition_id>/`，再用 `python -m etl.import_file` 匯入。
4. 網頁結構特殊才寫適配器（`crawler-framework.md` §6）：只做解析、不做 I/O、不寫死展覽名稱或網址（`tests/data/test_no_hardcoded_exhibition.py` 會檢查）。
5. 跑一次，確認 `crawler.store.verify_run(run_dir) == []`、`crawl_run.status`，再走 §3 的流程；品質關卡阻擋時看證據，不要硬發布。

### 4.2 來源改版或失效時

| 現象 | `crawl_run` 狀態／錯誤碼 | 處理 |
|---|---|---|
| 401／403／429、robots.txt 禁止 | `failed`／`access_blocked` | 不重試、不換標頭、不繞過；回報專案負責人，改用授權檔案或人工取得 |
| 404、410 | `failed`／`http_error` | 名單網址可能改了：重新評估來源，更新 `start_urls` |
| 5xx、逾時、網路錯誤 | `failed`／`http_error`、`timeout`、`network_error` | 已自動重試；之後再跑一次 |
| 欄位改名、表格不見、編碼錯誤 | `partial`／`parse_error`（快照已保存） | 用保存的快照更新對應設定或適配器，再從快照重建（`integrity-and-backup.md` §1） |
| 適配器程式錯誤 | `partial`／`unexpected` | 修適配器並補測試 |
| 回 200 但名單是空的、只剩表頭、名稱欄空白 | `succeeded`，0 筆 | 品質關卡 Q2 阻擋；檢查來源 |
| 名單大幅縮水 | `succeeded` | 品質關卡 Q3 阻擋；確認是真的縮水才 `accept={"Q3"}` |

失敗不會讓已發布的資料包消失或被取代：`latest_dataset_id` 只指向驗證通過的資料包，索引的 `last_acquisition` 與通知會說明這次發生什麼事（`quality-and-source-failures.md` §3）。

### 4.3 Schema 升版（共用檔案同步之後）

1. 依 `docs/architecture/module-boundaries.md` §4.3 同步共用檔案（含 `schemas/`），PR 附 §4.4 一致性檢查。
2. 讀 `schemas/CHANGELOG.md` 該版的相容性說明。驗證程式 R3 接受 `COMPATIBILITY.json` 的 `accepted`；新資料一律寫 `VERSION`。
3. `python data/samples/build_samples.py --force` 重新產生樣本（只會改 manifest 的 `schema_version`）。
4. `python -m tests.data.regression_outputs --write`，審查 `git diff tests/data/regression/`（預期只有 `schema_version` 改變）。
5. 三個 Python 版本（3.11／3.12／3.13）跑 `python -m pytest -q`。
6. 若 Schema 新增必填欄位或改變規則，先開 Issue 與專案負責人確認，**不得**在 `dev/data-platform` 改 `schemas/`。

### 4.4 修改資料端程式

- 先跑回歸測試；基準檔有差異時，只有在改變是刻意的才 `--write`，並在 PR 說明差異原因（`regression-tests.md` §4）。
- 新模組要有測試 import（`tests/data/test_regression.py` 會檢查每個 `crawler/`、`etl/` 模組）；新的命令列加入該檔的 `CLIS`。
- 驗證程式只有一份（`etl/validate.py`），不在別處另寫欄位清單或 Schema（`tests/data/test_skeleton.py` 會檢查）。
- 每個工作項目：實作 → 3 個 Python 版本測試 → 突變測試（腳本放 `/tmp`，加 timeout）→ `docs/data-platform/` 文件 → PR（base `dev/data-platform`）。

### 4.5 備份與還原

```bash
python -m etl.integrity backup --out backup.tar.gz data/packages/*/*/*/
python -m etl.integrity verify-backup backup.tar.gz
python -m etl.integrity restore backup.tar.gz restored/
```

備份前資料包必須通過驗證、引用的快照必須存在。企業登錄表、索引、歷史不在備份檔內：索引與歷史可由資料包重新產生；**企業登錄表要另外保存**（§2）。備份檔不可放到公開位置。保存位置尚未決定。

## 5. 不可以做的事

- 繞過 captcha、403／429、登入或付費牆；在 Git 放帳密或 token。
- 修改原始快照或已發布的資料包（兩者都不可變；要改就產生新的資料包）。
- 虛構筆數、企業資料、來源或信心值；官方筆數沒有來源就是 `null`。
- 修改 `schemas/`、`tests/contract/`、`CLAUDE.md`、`README.md`、`docs/`（`docs/data-platform/` 除外）、`knowledge/`、`skills/`、`reports/`、`site/`。
- 把資料端的 PR 合併到 `main`，或合併別人的 PR。

## 6. 待決事項（需要人決定）

| 事項 | 決定者 | 影響 |
|---|---|---|
| 是否恢復 D2-05（Actions 執行），連帶 D2-13、D3-03、D4-01 | Albert | 自動取得、品質關卡接入 workflow |
| 備份檔與大型快照的保存位置（Release、外部儲存） | 專案負責人 | `integrity-and-backup.md`、`snapshot-storage.md` |
| 第二個合法、結構不同的真實來源（D2-03）、真實取得（D2-02） | Albert | 通用性驗收需要真實資料 |
