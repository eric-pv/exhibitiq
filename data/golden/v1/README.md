# 黃金樣本 v1（A2-02）

**全部是合成資料（synthetic）**，用於整合測試與端到端驗收。負責人：Eric（`ai`）。

與 `schemas/v1/examples/` 結構不同的地方：檔案匯入取得（`csv_import`、`trigger: import`）、參展商下架（`listing_status: removed`）、缺少國家、官方筆數未知（`completeness_status: unknown`）、`co_exhibitor`、評分有三家企業。

| 檔案 | 內容 |
|---|---|
| `package/` | 輸入資料包（通過 R1～R11） |
| `dataset_index.json` | 指向本資料包的資料集索引（IR1～IR7） |
| `expected/analysis/analysis_result.json` | 預期的分析結果（AR1～AR9） |
| `expected/overview.json` | Dashboard 系統總覽應顯示的數字（由 site 的測試比對） |

本檔案同時作為 `sources.jsonl` 中示範快照的存放位置（`snapshot.locator`）。
