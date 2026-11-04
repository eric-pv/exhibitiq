# 合作夥伴、通路、競爭對手與潛在客戶（A2-08）

1. **初篩：** `exhibitiq_tools.py relate <package_dir>` 依 [`knowledge/relationship-rules@1.json`](../../../knowledge/relationship-rules@1.json)（草稿，待 Eric 核定）產生每家企業的候選關係，附訊號與來源 ID。結果只是候選。
2. **判斷依據：**
   - **競爭對手：** 企業的能力／技術分類詞與**已核定** BXR 產品卡的 `capabilities` 重疊。
   - **潛在客戶：** 企業的產業／應用／問題／需求分類詞與已核定產品卡的 `target_industries`、`applications`、`problems_addressed` 重疊。
   - **通路／合作夥伴：** 來源原文出現經銷、代理、系統整合等關鍵字。
   - 同時符合多種時依 `precedence` 取一種，其他列在 `other_candidates`，由 Skill 閱讀來源後決定。
3. **沒有已核定的 BXR 產品卡（A2-05）時，不得判定為競爭對手或潛在客戶**，一律寫 `unknown` 並說明原因。
4. **寫進分析結果時：** `relationships[]` 一律附 `evidence_source_ids`、`confidence`（只靠關鍵字時為 `low`）、引用的 `inference` 結論與不確定性（例如「分類詞與關係規則尚未核定」）。`evidence_check.py` 的 EV5 會檢查。
5. **競品分析：** 競爭對手清單只列有來源的事實（名稱、展位、來源分類、產品原文）；產品比較必須同時引用對方來源與 BXR 已核定產品卡，不得推測對方規格。
