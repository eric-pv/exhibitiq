# 分類規則（A2-06）

1. **輸入只用來源原文：** `participation.categories_as_listed`、`products_as_listed`、`exhibitor_name_as_listed`，以及有來源的企業描述。
2. **比對方式：** 對每個面向的分類詞，用 `label` 與 `synonyms` 做不分大小寫的完整詞比對（`exhibitiq_tools.py classify`）。這是**確定性的初篩**，結果一律是候選。
3. **寫進分析結果時：** 分類一律是 `inference`，`evidence_source_ids` 指向提供原文的來源；只有關鍵字比對、沒有其他佐證時，信心為 `low`。
4. **沒有命中：** 寫成 `unknown`，不要猜。
5. **核定：** `knowledge/taxonomy/` 目前是 `draft`。Eric 核定（`approval_status: approved`）之前，分類結果都要附一條不確定性：「分類詞尚未核定」。
6. **不寫回資料包：** 分類只存在分析結果，不修改來源事實。
