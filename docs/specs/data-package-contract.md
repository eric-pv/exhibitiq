# ExhibitIQ 資料包契約 v1（核心資料）

> 狀態：`1.0.0-draft.2`（Phase 1 草案期，依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) §3.1，任何變更都可能不相容）
> 負責人：專案負責人（`ai`）。Issue #7（P1-AI-04）。
> 機器可讀契約：[`schemas/v1/`](../../schemas/v1/)。本文件與 Schema 檔衝突時，以 Schema 檔為準，並視為需要修正的錯誤。
> AI 分析結果與證據引用契約見 [`analysis-result-contract.md`](analysis-result-contract.md)。

## 1. 範圍與讀者

本文件定義資料工程（`data`）產出、AI Skill（`ai`）讀取的**資料包**格式。資料工程依本文件實作爬蟲輸出、ETL、資料包產生與驗證程式；不需要閱讀 AI 端程式。

**同事的輸出是資料包；你的輸入是資料包。**（總規範 §5）

## 2. ID 規則

| ID | 格式 | 範例 | 產生方式 |
|---|---|---|---|
| `exhibition_id` | 小寫英數＋連字號，≤40 字元 | `mspo`、`tadte` | 人工指定，永不變更 |
| `edition_id` | `<exhibition_id>-<西元年>`，同年多屆可加小寫後綴 | `mspo-2026` | 由規則組成 |
| `dataset_id` | `<edition_id>.<UTC 建立時間 YYYYMMDDTHHMMSSZ>` | `mspo-2026.20261103T060000Z` | 由規則組成 |
| `company_id` | `co_` + ULID | `co_01JCC000000000000000000001` | ETL 指派 |
| `participation_id` | `pt_` + ULID | `pt_01JCP000000000000000000001` | ETL 指派 |
| `source_id` | `src_` + ULID | `src_01JCS000000000000000000001` | 擷取時指派 |
| `crawl_run_id` | `run_` + ULID | `run_01JCR000000000000000000001` | 擷取批次開始時指派 |
| `change_id` | `chg_` + ULID | `chg_01JCH000000000000000000001` | 變更比對時指派 |

- ULID：26 個字元，Crockford Base32（`0-9`、`A-Z` 去掉 `I L O U`），首字元 `0-7`。
- **`company_id` 必須穩定：** 一經指派永不變更、不重複使用、**不從名稱或網域推導**。同一家公司在不同展會、不同年度沿用同一個 `company_id`；ETL 需要維護自己的 ID 對照（存放方式由資料工程決定）。
- 名稱、網域或別名相似**不代表**同一家公司。確認為同一家時，將其中一筆設為 `status: "merged"` 並以 `merged_into` 指向保留的 ID，不得刪除。
- `participation_id` 對同一屆、同一企業應保持穩定，跨資料包重複使用。
- 每一次取得來源（每一份快照）都是新的 `source_id`；同一網址重新抓取也是新的 `source_id`。

## 3. 資料包目錄與檔案組成

```text
data/packages/<exhibition_id>/<edition_year>/<dataset_id>/
├── manifest.json          # 資料包清單（manifest.schema.json）
├── exhibition.json        # 1 筆（exhibition.schema.json）
├── edition.json           # 1 筆（edition.schema.json）
├── companies.jsonl        # 0..n 筆（company.schema.json）
├── participations.jsonl   # 0..n 筆（participation.schema.json）
├── sources.jsonl          # 1..n 筆（source.schema.json）
├── crawl_runs.jsonl       # 0..n 筆（crawl_run.schema.json）
└── changes.jsonl          # 0..n 筆（change.schema.json）
```

- **8 個檔案全部必備。** 沒有紀錄的 JSONL 檔是 0 位元組的空檔，不可省略。
- 一個資料包只涵蓋**一個屆次**。
- 資料包建立後不得修改；資料更新時產生新的 `dataset_id`，以 `previous_dataset_id` 串連。
- `companies.jsonl` 只收錄本屆有參展紀錄、或被 `merged_into` 參照的企業。
- 資料包存放於 Git、Releases 或其他位置，屬於資料工程的儲存策略（總規範 §4）；不論放在哪裡，目錄內容都依本節組成。

## 4. 實體摘要

完整欄位、型別與限制以 Schema 檔為準。所有紀錄型物件都是 `additionalProperties: false`：**未定義的欄位一律拒絕**，需要新欄位時依 [`VERSIONING.md`](../../schemas/VERSIONING.md) §5 提出。

| 實體 | 必填欄位 | 重點 |
|---|---|---|
| `exhibition` | `exhibition_id`、`name`、`source_ids`、`verification_status` | 跨年度不變的展覽本體 |
| `edition` | `edition_id`、`exhibition_id`、`year`、`source_ids`、`verification_status` | 日期、場地 |
| `company` | `company_id`、`name`、`status`、`source_ids`、`verification_status` | 別名、網域；`merged` 必須有 `merged_into`，`active` 不得有 |
| `participation` | `participation_id`、`company_id`、`edition_id`、`exhibitor_name_as_listed`、`participation_type`、`listing_status`、`source_ids`、`verification_status` | 保留來源原文（`*_as_listed`）；下架以 `listing_status: "removed"` 表示，不刪除 |
| `source` | `source_id`、`source_type`、`retrieved_at`、`content_sha256`、`snapshot` | 非 `manual_entry` 必須有 `url`；`manual_entry` 與 `not_stored` 必須有 `notes` |
| `crawl_run` | `crawl_run_id`、`exhibition_id`、`edition_id`、`crawler`、`trigger`、`started_at`、`finished_at`、`status`、`stats` | 只收錄已結束的批次；詳細執行日誌格式由資料工程定義 |
| `manifest` | 見第 9、10 節 | 涵蓋總規範 §6 的 9 個必要欄位 |
| `change` | `change_id`、`dataset_id`、`previous_dataset_id`、`entity_type`、`entity_id`、`change_type`、`detected_at` | `modified` 必須有 `field_changes` |

**選填欄位：** 取不到值就**省略該欄位**，不要填 `null` 或空字串。只有 Schema 明確允許 `null` 的欄位可以是 `null`（`manifest.previous_dataset_id`、`manifest.completeness` 的官方筆數欄位）。

**共通格式：**
- 時間：UTC，RFC 3339，以 `Z` 結尾（`2026-11-03T06:00:00Z`）；日期：`YYYY-MM-DD`。
- 國家：ISO 3166-1 alpha-2 大寫；合成資料使用 `ZZ`。
- 文字欄位不可為空字串或只有空白。

## 5. 序列化

- 編碼 UTF-8，**不加 BOM**；換行只用 LF。
- `*.jsonl`：每行一筆，每行（包括最後一行）以 `\n` 結尾；空檔為 0 位元組。
- `exhibition.json`、`edition.json`：同樣是一行 canonical JSON 加 `\n`。
- 每一行的 canonical 形式等同於 Python：

  ```python
  json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
  ```

- JSONL 紀錄依主鍵（`company_id`、`participation_id`、`source_id`、`crawl_run_id`、`change_id`）以 UTF-8 位元組順序遞增排列，主鍵不可重複。
- `manifest.json` 不參與 `content_hash`，格式不限；建議 `indent=2`。

目的：相同輸入產生相同位元組，`content_hash` 才能重現。

## 6. 雜湊計算

所有雜湊值都寫成 `sha256:` 加 64 個小寫十六進位字元。

- **`files.<檔名>.sha256`：** 該檔案原始位元組的 sha256。另記 `bytes`（位元組數）與 `records`（JSONL 為行數，`.json` 為 1）。
- **`content_hash`：** 對 7 個資料檔（不含 `manifest.json`），依檔名的位元組順序產生 `<64 位十六進位>␣␣<檔名>\n` 清單，再對整份清單取 sha256。等同於在資料包目錄執行：

  ```bash
  sha256sum changes.jsonl companies.jsonl crawl_runs.jsonl edition.json exhibition.json participations.jsonl sources.jsonl | LC_ALL=C sort -k2 | sha256sum
  ```

  輸出前面加上 `sha256:`。
- **`source.content_sha256`：** 來源快照原始位元組（下載回來、尚未解析的內容）的 sha256；`manual_entry` 則為輸入內容的 sha256。
- 空檔的 sha256 是 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

## 7. 來源追溯

- 每一筆事實紀錄（展覽、屆次、企業、參展紀錄）都必須有 `source_ids`（至少 1 個）。
- 個別欄位來自不同來源時，用 `field_sources` 標示：`{"website": ["src_…"]}`。未列出的欄位以紀錄層級的 `source_ids` 為準。別名另有自己的 `source_ids`。
- 所有被引用的 `source_id` 都必須存在於同一資料包的 `sources.jsonl`；`manifest.source_snapshot_ids` 必須與 `sources.jsonl` 的 ID 集合**完全相同**。
- `source.snapshot` 記錄原始快照存放位置：`git`、`release`、`actions_artifact`、`external` 時必須有 `locator`；Actions Artifact 會過期，應填 `retained_until`。未保存快照時為 `not_stored`，並在 `notes` 說明原因。
- 原始快照不可變更（總規範：Raw evidence is immutable）。

## 8. 查證狀態

核心資料的 `verification_status` 只能是：

| 值 | 意義 | 誰可以寫 |
|---|---|---|
| `unverified` | 已取得來源，尚未核對 | 爬蟲／ETL（預設值） |
| `verified` | 已與官方或第一手來源核對 | ETL（有可重現的核對規則時） |
| `human_confirmed` | 經人工確認 | 人工 |
| `insufficient_data` | 來源不足以確認 | 爬蟲／ETL |

**核心資料不得出現 `ai_inferred`。** AI 推論只能寫在分析結果（P1-AI-05），不得覆蓋或寫回資料包中的來源事實。

## 9. 完整性

`manifest.completeness_status`：

| 值 | 條件 |
|---|---|
| `complete` | 已取得官方公布的參展商數（`official_exhibitor_count` 與 `official_count_source_id` 皆非 null），且等於 `listing_status: "listed"` 的參展紀錄數 |
| `partial` | 已知不完整，例如官方公布 100 家只取得 80 家 |
| `unknown` | 無法確認完整度，例如官方沒有公布數字 |

- `completeness.collected_participation_count` 必須等於 `listing_status: "listed"` 的參展紀錄數。
- 官方筆數必須有來源（`official_count_source_id` 存在於 `sources.jsonl`），否則 `official_exhibitor_count` 為 `null`。**不得用估計值或歷史討論數字填入。**

## 10. Schema 版本宣告

- `manifest.schema_version` 是整個資料包的版本宣告；JSONL 紀錄**不**逐筆攜帶 `schema_version`。
- 草案期必須與 [`schemas/v1/VERSION`](../../schemas/v1/VERSION) 完全相同（目前 `1.0.0-draft.2`），`manifest.schema.json` 以 `const` 強制。
- `manifest.data_origin`：`collected`（實際擷取）或 `synthetic`（合成測試資料）。**合成資料不得作為分析事實。**

## 11. 變更紀錄

- `changes.jsonl` 記錄本資料包相對於 `previous_dataset_id` 的差異。
- 第一個資料包（`previous_dataset_id: null`）的 `changes.jsonl` 必須是空檔。
- 每筆變更的 `dataset_id`、`previous_dataset_id` 必須與 manifest 相同。
- `change_type: "modified"` 必須列出 `field_changes`（`field`、`before`、`after`）。

## 12. 資料包驗證規則

資料工程的驗證程式（位於 `etl/`）至少要檢查以下規則。規則編號與 `tests/contract/package_check.py` 相同。

| 編號 | 規則 |
|---|---|
| R1 | 第 3 節的 8 個檔案全部存在 |
| R2 | `manifest.json` 通過 `manifest.schema.json` |
| R3 | `schema_version` 與 `schemas/v1/VERSION` 相同（草案期） |
| R4 | 每一筆紀錄通過對應的 Schema；`exhibition.json`、`edition.json` 各剛好 1 筆 |
| R5 | 序列化符合第 5 節（UTF-8 無 BOM、LF、結尾換行、canonical 形式） |
| R6 | JSONL 主鍵不重複，並依位元組順序排列 |
| R7 | `record_counts` 與 JSONL 行數相同 |
| R8 | `files` 的 `sha256`、`bytes`、`records` 與實際檔案相同；`content_hash` 依第 6 節重新計算後相同 |
| R9 | `exhibition.json`、`edition.json` 的 ID 與年份和 manifest 一致；`dataset_id` 以 `<edition_id>.` 開頭 |
| R10 | 參照完整性：所有 `source_ids`、`field_sources`、別名來源都在 `sources.jsonl`；`source_snapshot_ids`、`crawl_run_ids` 與對應檔案的 ID 集合相同；`participation.company_id`、`merged_into` 在 `companies.jsonl`；`source.crawl_run_id` 在 `crawl_runs.jsonl`；參展紀錄、擷取批次的 `edition_id` 與 manifest 相同；變更紀錄的資料包 ID 與 manifest 相同；第一個資料包沒有變更紀錄 |
| R11 | 完整性規則（第 9 節） |

Schema 載入方式：從本機 `schemas/v1/` 載入全部 `*.schema.json`，依各檔的 `$id` 建立 registry（Python `jsonschema` + `referencing`）；`$id` 使用保留網域 `exhibitiq.invalid`，**不得透過網路取得**。日期與時間以 Schema 的 `pattern` 為準，不依賴 `format` 檢查套件。

## 13. 範例

[`schemas/v1/examples/`](../../schemas/v1/examples/) 內的資料**全部是合成資料**（`data_origin: "synthetic"`、國家 `ZZ`、網址 `example.com`／`example.org`），不代表任何真實展覽或企業：

- `examples/package/`：完整、通過 R1–R11 的資料包，可以作為產生器輸出比對與驗證程式的測試向量。
  - `content_hash` = `sha256:68fc94dcaeaed1d23842f327b6b3cd05e07cca6610372ebb086622b03fb4d74b`
  - 包含：多來源欄位（`field_sources`）、別名、未列展位的參展紀錄、`not_stored` 快照、空的 `changes.jsonl`、`partial` 完整度
- `examples/change.example.json`：第二個資料包中的一筆 `modified` 變更紀錄。

範例會隨 `schemas/` 同步到 `dev/data-platform`；`tests/contract/` 則不同步。

## 14. 資料工程實作檢查清單

- [ ] 資料包產生器依第 3、5、6 節輸出，並可重現相同的 `content_hash`
- [ ] 驗證程式涵蓋第 12 節 R1–R11，從本機載入 `schemas/v1/`
- [ ] 驗證程式以 `schemas/v1/examples/package/` 作為正向測試向量
- [ ] `company_id` 指派與對照機制能跨資料包保持穩定
- [ ] 下架的參展紀錄以 `listing_status: "removed"` 保留
- [ ] 官方筆數有來源才填寫；否則 `null` 並標示 `unknown` 或 `partial`
- [ ] `data/samples/mspo/` 的合成資料標示 `data_origin: "synthetic"`

## 15. 已知限制與待決事項

- 草案期間欄位可能調整；每次變更都會更新 `VERSION`、`CHANGELOG.md`，並重新同步。
- 產業、技術等**正規化分類**不在本契約內，參展紀錄只保留來源原文（`categories_as_listed`）；分類架構屬於 P1-AI-06。
- 資料包的存放位置索引與保留策略屬於資料工程 Phase 2 工作，本契約只定義目錄內容。
- `tests/contract/package_check.py` 只是用來證明範例符合契約的參考檢查，不是專案的資料驗證程式。
