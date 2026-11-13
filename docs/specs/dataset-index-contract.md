# ExhibitIQ 資料集索引與管線狀態契約 v1

> 狀態：`1.0.0-draft.5`（Phase 1 草案期，依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) §3.1）
> 負責人：專案負責人（`ai`）。工作項目 A1-07。
> 機器可讀契約：[`schemas/v1/dataset_index.schema.json`](../../schemas/v1/dataset_index.schema.json)。本文件與 Schema 衝突時，以 Schema 為準。

## 1. 用途

一個檔案回答「系統裡有哪些展覽、每個展覽的資料怎麼取得、最近一次取得成功還是失敗、有哪些可用的資料包、驗證過了沒」。

- **產生者：** 資料工程（D2-12），每次取得、匯入或驗證後重新產生。
- **讀取者：** Dashboard 的展覽搜尋、展覽情報與「資料及系統狀態」頁（W2-01、W2-05）；Skill 找最新資料包（A2-04）。
- **存放位置：** `data/index/datasets.json`。

Dashboard **只從這個檔案取得展覽清單**，不寫死任何展覽（總規範 §1.1、開發計畫 §6）。

## 2. 結構

```text
dataset_index
├── schema_version、generated_at、generator
├── exhibitions[]                          已登錄的展覽
│   ├── exhibition_id、name、name_zh_hant、country、website
│   ├── acquisition                        取得方式與來源評估結果
│   └── editions[]
│       ├── edition_id、year、latest_dataset_id
│       ├── last_acquisition               最近一次取得結果（包括失敗）
│       └── datasets[]                     資料包摘要（與 manifest 相同的數值）＋ validation
└── notices[]                              給系統狀態頁的通知（info／warning／error）
```

## 3. 取得方式與來源評估（`acquisition`）

| 欄位 | 值 |
|---|---|
| `method` | `automatic`（爬蟲）、`semi_automatic`（需要人工步驟）、`file_import`（公開的 PDF、CSV、Excel）、`authorized_file`（主辦單位授權提供）、`manual_entry`（人工輸入）、`undetermined`（尚未決定） |
| `status` | `not_assessed`、`feasible`、`partially_feasible`、`not_feasible`、`pending_authorization` |
| `assessed_at`、`report_path` | 已評估（`status` 不是 `not_assessed`）時必填；`report_path` 是評估報告在 repo 內的路徑，例如 `docs/data-platform/<exhibition_id>-source-assessment.md` |
| `notes` | `partially_feasible`、`not_feasible`、`pending_authorization` 時必填，說明原因 |

## 4. 最近一次取得結果（`last_acquisition`）

`method`、`status`（`succeeded`、`partial`、`failed`、`cancelled`）、`finished_at`；選填 `crawl_run_id`、`records_extracted`、`error_count`、`dataset_id`、`notes`。

- **取得失敗也要記錄。** `failed` 時必須有 `notes` 說明原因，而且**不能**有 `dataset_id`（失敗不會產生資料包）。
- 欄位對應 `crawl_run`（`status`、`stats.records_extracted`、`stats.error_count`、`finished_at`）；匯入或人工輸入沒有 `crawl_run_id` 時省略。

## 5. 資料包摘要（`datasets[]`）

`dataset_id`、`location`（`storage`：`git`／`release`／`actions_artifact`／`external`，加上 `locator`）、`created_at`、`data_origin`、`schema_version`、`content_hash`、`record_counts`（companies、participations、sources）、`completeness_status`、`official_exhibitor_count`、`collected_participation_count`、`validation`。

- 數值必須和該資料包的 `manifest.json` 相同（IR6）。
- `validation.status`：`passed`、`failed`、`not_run`。`passed` 與 `failed` 必須有 `validated_at`、`validator`、`error_count`；`failed` 必須有 `messages`（最多 20 筆）。
- `latest_dataset_id` 是**驗證通過**的資料包中 `created_at` 最新的一個；沒有通過的資料包時為 `null`。驗證失敗的資料包仍然列出，讓 Dashboard 顯示失敗原因，但不會成為最新資料包。

## 6. 驗證規則

規則編號與 `tests/contract/index_check.py` 相同。

| 編號 | 規則 |
|---|---|
| IR1 | 通過 `dataset_index.schema.json`（第 3～5 節的必填條件由 Schema 強制） |
| IR2 | `schema_version` 與 `VERSION` 相同 |
| IR3 | 展覽、屆次、資料包 ID 不重複；`edition_id` 以 `<exhibition_id>-` 開頭並包含年份；`dataset_id` 以 `<edition_id>.` 開頭 |
| IR4 | `latest_dataset_id` 是最新的驗證通過資料包，沒有時為 `null` |
| IR5 | `last_acquisition.dataset_id` 必須在 `datasets[]` 中 |
| IR6 | 存放在 Git 的資料包：摘要數值與 manifest 相同；標記 `passed` 的資料包必須真的通過資料包規則 R1～R11 |
| IR7 | 通知引用的展覽與資料包必須存在 |

正式的索引產生與驗證屬於資料工程（D2-12）；`index_check.py` 只是用來證明範例符合契約的參考檢查。

## 7. 範例

[`schemas/v1/examples/index/dataset_index.example.json`](../../schemas/v1/examples/index/dataset_index.example.json)，**全部是合成資料**：

- `example-expo`：可自動擷取，最近一次取得成功，指向 `schemas/v1/examples/package/`，完整度 `partial`。
- `sample-fair`：評估為 `not_feasible`，最近一次取得失敗（403），沒有資料包，`latest_dataset_id` 為 `null`。

兩個展覽的 `report_path` 都指向本文件，只是示範格式；真實展覽要指向實際的評估報告。

## 8. 不包含

- 「新增展覽」的登錄資料見 [`exhibition-registry-contract.md`](exhibition-registry-contract.md)（A1-10）。資料集索引只列出 `accepted` 的登錄（RG6）。
- 事件日誌（D1-07 的 JSONL）不在契約內；系統狀態頁需要的內容以 `last_acquisition` 和 `notices` 提供。
