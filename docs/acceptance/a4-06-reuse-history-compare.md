# 模組共用、歷史版本與跨展覽比較驗證（A4-06）

> 驗證日期：2026-11-10｜負責人：專案負責人（`ai`）｜狀態以 `dev/ai-intelligence` 為準；每一項都由自動測試強制。

## 1. 模組共用（同一份程式，不各自重做）

| 項目 | 怎麼確保只有一份 | 證據 |
|---|---|---|
| 設計樣式 | 顏色、間距、字級只定義在 `site/src/theme/tokens.ts` | `site/src/app.test.tsx`「colours are defined only in theme/tokens.ts」 |
| 報告 | 網頁、PDF、Markdown 用同一份分析結果與同一份版型；數據摘要文字兩邊相同 | `site/src/reports.test.tsx` |
| 關鍵字比對規則 | 網站與 Python 同一套規則，結果相同 | `site/src/compare.test.tsx`「keyword rule matches the Python rule」、比較計數與 Python `compare` 相同 |
| 分析設定雜湊 | 瀏覽器與 Python 算出相同雜湊 | `site/src/settings.test.tsx`、`tests/contract/test_analysis_profile_v1.py` |
| 資料存取 | 頁面只透過 `site/src/data/` 讀資料；bundle 先用 `schemas/` 驗證 | `site/src/golden.test.ts`、bundle 驗證失敗即停止 |
| 分析工具 | Skill、網站「執行分析」、測試都呼叫同一組 `exhibitiq_tools.py` 指令 | `tests/contract/test_skill_tools.py`、`test_session_tools.py` |

## 2. 歷史版本（每個版本都可追溯，不覆蓋）

| 項目 | 行為 | 證據 |
|---|---|---|
| 資料包版本 | 同一屆次有多個版本時，頁面使用最新驗證通過的版本；舊版本仍列在系統狀態頁（ID、雜湊、驗證結果） | `site/src/versions.test.tsx`（本次新增） |
| 分析結果 | 存檔後不能修改（只能更新審核欄位）；重新分析必須用新的 ID，舊結果保留 | `tests/contract/test_save_analysis.py` |
| 可重現 | 所有確定性輸出的雜湊固定，在另一個乾淨工作區重算一致 | `tests/contract/test_repro.py`、`repro_check.py --check` |
| 報告追溯 | 附錄列出 Schema、Skill、模型、知識庫、版型、輸入資料包與雜湊、分析設定雜湊 | `tests/contract/test_skill_tools.py`（appendix）、`site/src/reports.test.tsx` |

## 3. 跨展覽與跨年度比較

| 項目 | 行為 | 證據 |
|---|---|---|
| 不同結構的兩個展覽並排比較 | 同一組指標；沒有資料包的屆次顯示「資料不足」；資料不完整時不算比例 | `site/src/compare.test.tsx`、`tests/contract/test_compare.py` |
| 同一展覽的歷史趨勢 | 「再次參展」是事實；前一年／後一年不完整時不判斷新參展／未再參展；只有一年時顯示資料不足 | `tests/contract/test_history.py`、`site/src/compare.test.tsx`（history） |
| 任何分析主題都能比較 | 不依賴 BXR 產品卡 | `tests/contract/test_compare.py`（industry profile） |

## 4. 尚待真實資料補強
- 目前跨展覽比較使用合成資料與黃金樣本；第二個真實展覽（Albert #114）完成並經階段整合後，以兩個真實展覽重跑本表的比較項目（A4-10）。
