# 企業關係（A2-16，取代 A2-08 的單一標籤規則）

1. **一律依分析設定檔：** `exhibitiq_tools.py relate <package_dir> --profile <profile_id>`（`skills/exhibitiq/scripts/profile_tools.py`）。修改關鍵字或訊號只改 `knowledge/analysis-profiles/`，不改程式。
2. **多標籤：** 同一家企業可以同時是潛在客戶、競爭對手、合作夥伴、通路；沒有任何訊號時只有一筆「待判斷」（`unknown`）。**不設優先順序。**
3. **訊號來源：**
   - 設定檔 `relationship_signals` 的訊號詞（四種關係各自設定）。
   - 類別為 `competitor` 的關鍵字 → 競爭對手候選。
   - **只有 A 模式：** 類別為 `product` 的關鍵字（BXR 產品功能定位）→ 競爭對手候選；類別為 application／industry／need／problem 的關鍵字 → 潛在客戶候選。產品卡未核定時，`bxr_products_status` 為 `draft`，報告必須提示。
   - B、C 模式不讀 BXR 產品卡。
4. **命中只是候選：** 每筆候選附訊號、來源 ID、理由與資料充分程度（`sufficiency: signal_only`）、信心 `low`。Skill 必須閱讀來源後才寫進分析結果的 `relationships[]`（一律 `inference`，EV5 檢查來源與信心）；不能確認就寫 `unknown`。
5. **競品分析：** 只列有來源的事實；產品比較必須同時引用對方來源與 BXR 產品卡，不得推測對方規格。

`knowledge/relationship-rules@1.json` 已停用（訊號詞移到各分析設定檔），保留作為歷史紀錄。
