# knowledge/bxr-products/ — BXR 產品知識庫

- **負責人：** Eric（`ai`）。格式：[`schemas/v1/bxr_product.schema.json`](../../schemas/v1/bxr_product.schema.json)；規格：[`docs/specs/knowledge-base-contract.md`](../../docs/specs/knowledge-base-contract.md)。
- **目前狀態：** 只有結構，**沒有任何產品卡**。產品內容要由 Eric 提供依據文件（型錄、規格書等），經核定後才建立（A2-05）。

## 規則

- 每個產品一個檔案：`<product_id>.json`，`product_id` 格式為 `bxr-<小寫英數與連字號>`。
- 內容只能來自 `sources[]` 列出的內部文件；**每一項規格都要指向依據文件**，不得自行推測規格或能力。
- 只有 `approval_status: "approved"`（並有 `approved_by`、`approved_at`）的產品卡可以被分析與 Dashboard 使用。
- 能力、應用、產業、問題欄位只能引用 `knowledge/taxonomy/` 中已核定的分類詞。
- 格式範例（合成）：[`schemas/v1/examples/knowledge/bxr_product.example.json`](../../schemas/v1/examples/knowledge/bxr_product.example.json)。
