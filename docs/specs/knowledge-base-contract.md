# ExhibitIQ 知識庫契約 v1（BXR 產品與分析分類）

> 狀態：`1.0.0-draft.5`（Phase 1 草案期，依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) §3.1）
> 負責人：Eric（`ai`）。工作項目 A1-09。
> 機器可讀契約：[`schemas/v1/bxr_product.schema.json`](../../schemas/v1/bxr_product.schema.json)、[`schemas/v1/taxonomy.schema.json`](../../schemas/v1/taxonomy.schema.json)。

## 1. 用途與原則

- **BXR 產品卡：** 分析時用來比對企業需求與 BXR 產品（產品適配、展品建議）。
- **分析分類：** 產業、技術、應用、能力、問題、需求六個面向的標準詞彙，讓不同展覽的資料用同一組分類比較。
- **內容只能來自 Eric 提供並核定的文件，不得自行推測產品規格或能力。** A1-09 只建立結構，`knowledge/` 中**沒有任何產品卡**，分類檔也都是空的草稿。
- 分類是分析用的詞彙，**不是來源事實**：企業被歸入某個分類，屬於 AI 推論（分析結果契約的 `inference`）。

## 2. 存放位置

```text
knowledge/
├── bxr-products/<product_id>.json   產品卡（bxr_product.schema.json）；目前沒有
└── taxonomy/<dimension>.json        6 個分類面向（taxonomy.schema.json）；目前都是空的 draft
```

## 3. 產品卡

| 欄位 | 必填 | 說明 |
|---|---|---|
| `schema_version` | ✅ | 等於 `schemas/v1/VERSION` |
| `product_id` | ✅ | `bxr-<小寫英數與連字號>`，檔名必須是 `<product_id>.json` |
| `name`、`summary` | ✅ | |
| `name_en`、`product_line` | | |
| `capabilities`、`applications`、`target_industries`、`problems_addressed` | | 只能引用對應面向的分類詞（`capability.*`、`application.*`、`industry.*`、`problem.*`） |
| `specifications[]` | | `name`、`value`、`unit`、**`source_index`（必填，指向 `sources[]`）**：每一項規格都要有依據文件 |
| `sources[]` | ✅（≥1） | 依據文件：`title`、`provided_by`、`provided_at`，選填 `version`、`path` |
| `approval_status` | ✅ | `draft`、`pending_review`、`approved`、`retired`；`approved` 必須有 `approved_by`、`approved_at` |
| `updated_at` | ✅ | |

## 4. 分析分類

每個面向一個檔案：`dimension`、`approval_status`（同上）、`terms[]`。

- `term_id`：`<dimension>.<slug>`，例如 `capability.scenario-training`；同一檔案內不重複，前綴必須是該檔案的面向。
- `label`（必填）、`label_en`、`parent_id`（同一檔案內的上層分類）、`synonyms`、`description`。

## 5. 驗證規則

規則編號與 `tests/contract/knowledge_check.py` 相同。

| 編號 | 規則 |
|---|---|
| KB1 | 通過對應 Schema（`approved` 必須有核定人與日期、規格必須有 `source_index` 等，由 Schema 強制） |
| KB2 | `schema_version` 等於 `VERSION` |
| KB3 | 分類：檔名等於面向；`term_id` 不重複、前綴正確；`parent_id` 存在 |
| KB4 | 產品：檔名等於 `product_id`；各欄位只引用對應面向的分類詞 |
| KB5 | 規格的 `source_index` 指向存在的依據文件 |
| KB6 | **核定的產品卡只能引用已核定分類檔中的分類詞** |
| AR10 | **分析結果的建議（`product_ids`）只能引用已核定的產品卡**（補充分析結果契約） |

## 6. 範例

[`schemas/v1/examples/knowledge/`](../../schemas/v1/examples/knowledge/)：一個合成的 `capability` 分類檔與一張合成產品卡（`draft`）。**全部是虛構內容，只用來示範格式。**

## 7. 之後的工作

- **A2-05：** Eric 提供 BXR 產品資料（型錄、規格書等）後建立產品卡並核定。
- **A2-06：** 建立各面向的分類詞並核定。
