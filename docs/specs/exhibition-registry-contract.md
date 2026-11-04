# ExhibitIQ 展覽登錄契約 v1（展覽名冊）

> 狀態：`1.0.0-draft.5`（Phase 1 草案期）｜負責人：Eric（`ai`）定義格式；Albert（`data`）的流程寫入。工作項目 A1-10。
> 機器可讀契約：[`schemas/v1/exhibition_registration.schema.json`](../../schemas/v1/exhibition_registration.schema.json)。

## 1. 登錄資料是什麼

使用者在 Dashboard 的「展覽搜尋與新增」（W3-07）或 GitHub Actions（D2-13）新增一個展覽時留下的一筆基本資料，也就是**展覽名冊的一筆**：要處理哪個展覽、哪幾個年份、從哪個官網開始找來源、誰在什麼時候提出。

- **不是帳號，也不含任何個人資料或密碼。** `requested_by` 只寫名字或角色。
- **不是來源事實。** 使用者輸入的名稱、國家、官網只是來源探索的起點；展覽的日期、場地、參展商等事實，一律來自取得後的資料包（`exhibition.json`、`edition.json`，必須有 `source_ids`）。

## 2. 存放位置（Eric 於 2026-11-04 決定：一個大資料夾，每個展覽一個小資料夾）

```text
data/registry/                        展覽名冊（data 負責寫入）
├── <exhibition_id>/
│   ├── registration.json             登錄資料（本契約）
│   └── …                             該展覽的其他資料（例如來源評估報告，由 data 決定）
└── <另一個 exhibition_id>/
```

- 資料夾名稱必須等於 `exhibition_id`；每個資料夾都必須有 `registration.json`。
- 一個展覽一個資料夾，同時新增不同展覽不會互相衝突。
- 新增或修改登錄資料，一律透過資料更新 PR（D2-13），不直接寫 `main`。

## 3. 欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `schema_version` | ✅ | 等於 `schemas/v1/VERSION` |
| `exhibition_id` | ✅ | 小寫英數與連字號，例如 `example-expo`；**指派後永不變更**。由新增流程依名稱或官網產生，重複時加後綴 |
| `name` | ✅ | 使用者輸入的名稱原文 |
| `name_zh_hant`、`name_en` | | |
| `country` | | ISO 3166-1 alpha-2 |
| `website` | | 官方網站（http/https）；**只是來源探索的起點，不代表已查證** |
| `years` | ✅ | 要處理的年份，至少一個，不重複 |
| `registration_status` | ✅ | `requested`（剛提出）、`accepted`（已接受，進入來源評估與取得）、`rejected`（重複或無效，**必須有 `notes`**）、`retired`（不再處理） |
| `duplicate_of` | | 判定為重複時，指向已接受的 `exhibition_id`；只能用在 `rejected` |
| `requested_by`、`requested_at` | ✅ | 提出者（名字或角色）、提出時間（UTC） |
| `request_channel` | ✅ | `dashboard_form`、`actions_dispatch`、`manual` |
| `notes` | | |

**刻意不放的欄位：** 日期、場地、參展商數量、`source_ids`、查證狀態。這些是來源事實，只能出現在資料包。

## 4. 和其他契約的對應

| 登錄資料 | 對應 | 說明 |
|---|---|---|
| `exhibition_id` | `exhibition.exhibition_id`、資料集索引 `exhibitions[].exhibition_id` | 同一個 ID 貫穿全部檔案 |
| `years[]` | `edition.edition_id` = `<exhibition_id>-<year>`、資料集索引 `editions[]` | 每個登錄的年份都要在資料集索引中有一個 edition（還沒取得時 `datasets` 為空、`latest_dataset_id` 為 `null`） |
| `name`、`country`、`website` | 資料集索引的 `name`、`country`、`website` | 取得資料前先用登錄資料顯示；取得後的事實以資料包為準 |
| `registration_status: accepted` | 資料集索引 `exhibitions[]` | **只有 accepted 的登錄會出現在資料集索引**；尚未評估時 `acquisition.status` 為 `not_assessed` |
| 取得結果 | 資料集索引 `acquisition`、`last_acquisition` | 登錄資料**不記錄**取得成功或失敗 |

## 5. 新增展覽的流程

1. 使用者在 Dashboard 填寫名稱、國家、年份、官網 → 產生登錄內容並連到 GitHub Actions（W3-07）；或直接在 Actions 輸入（D2-13）。
2. D2-13 workflow 產生 `exhibition_id`、檢查是否重複，寫入 `data/registry/<exhibition_id>/registration.json`，以資料更新 PR 提交。
3. 合併後，通用來源探索與可行性評估（D1-11）→ 擷取或匯入（D2-02、D2-04）→ 資料包 → 資料集索引 → Dashboard。
4. 任何一步失敗都記錄在資料集索引，不阻礙其他展覽（總規範 §1.1）。

## 6. 驗證規則

規則編號與 `tests/contract/registry_check.py` 相同。

| 編號 | 規則 |
|---|---|
| RG1 | 通過 Schema（`rejected` 必須有 `notes`、年份不重複等） |
| RG2 | `schema_version` 等於 `VERSION` |
| RG3 | 資料夾名稱等於 `exhibition_id`；每個資料夾都有 `registration.json` |
| RG4 | `duplicate_of` 只能用在 `rejected`，且不能指向自己 |
| RG5 | `duplicate_of` 必須指向一個 `accepted` 的登錄 |
| RG6 | 資料集索引**剛好**列出所有 `accepted` 的登錄，而且每個登錄年份都有對應的 edition |

## 7. 範例

[`schemas/v1/examples/registry/`](../../schemas/v1/examples/registry/)：兩個已接受的展覽（對應範例資料集索引）與一個被判定為重複的登錄。全部是合成資料。
