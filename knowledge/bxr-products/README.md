# knowledge/bxr-products/ — BXR 產品知識庫

- **負責人：** Eric（`ai`）。格式：[`schemas/v1/bxr_product.schema.json`](../../schemas/v1/bxr_product.schema.json)；規格：[`docs/specs/knowledge-base-contract.md`](../../docs/specs/knowledge-base-contract.md)。
- **目前狀態（A2-05，V2.5）：** 8 張產品卡，全部是 **`draft`（待審核）**，只有 Eric 提供的產品名稱與初始功能定位；**沒有任何規格數值**。正式型錄提供並經 Eric 核定後，才改為 `approved`。
- **用途：** 只用於 A 模式（BXR 商機分析，主題 `knowledge/analysis-profiles/bxr-opportunity.json`）；使用未核定產品卡的報告必須提示「產品資料未核定」。B、C 模式不使用產品卡。

## 規則

- 每個產品一個檔案：`<product_id>.json`，`product_id` 格式為 `bxr-<小寫英數與連字號>`。
- 內容只能來自 `sources[]` 列出的內部文件；**每一項規格都要指向依據文件**，不得自行推測規格或能力。
- 只有 `approval_status: "approved"`（並有 `approved_by`、`approved_at`）的產品卡可以被分析與 Dashboard 使用。
- 能力、應用、產業、問題欄位只能引用 `knowledge/taxonomy/` 中已核定的分類詞。
- 格式範例（合成）：[`schemas/v1/examples/knowledge/bxr_product.example.json`](../../schemas/v1/examples/knowledge/bxr_product.example.json)。
