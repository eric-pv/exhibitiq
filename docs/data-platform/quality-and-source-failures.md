# 資料品質與來源失效測試

> 工作項目：D4-07｜負責人：data｜程式：`etl/quality.py`｜測試：`tests/data/test_quality_and_failures.py`
> 本文件只記錄已實作並測試過的行為。

## 1. 發現的風險

逐一模擬來源失效時發現：**來源回 200 但內容是空的**（CSV 只剩表頭、名稱欄全部空白），爬蟲依 D2-01 的規則回報 `succeeded`、0 筆，而後續流程沒有任何東西阻止一個近乎空的資料包成為該屆的最新版本（D2-12 的 `latest_dataset_id` 是「驗證通過且最新」）。名單大幅縮水（例如網站改版只抓到一部分）也一樣。

## 2. 品質關卡：`etl.quality.check_acquisition`

在組裝新資料包之前呼叫，輸入**這一次**取得的 crawl run、最終的參展紀錄（`carry_forward` 之後）與前一個資料包的參展紀錄：

| 代碼 | 等級 | 條件 |
|---|---|---|
| Q1 | block | 任一 crawl run 為 `failed` 或 `cancelled`（附第一筆錯誤訊息） |
| Q2 | block | 沒有任何 `listed` 參展紀錄 |
| Q3 | block | `listed` 數比前一個資料包少超過 `max_drop_ratio`（預設 50%；被攜帶為 `removed` 的不算） |
| Q4 | warn | crawl run 為 `partial` |
| Q5 | warn | 擷取列數多於 `listed` 參展紀錄（同一企業被合併，或列被略過） |

- `block` = 不自動發布，由人先看證據。關卡**不判斷**縮水是真的還是錯的，只是不讓它無聲通過；不刪除、不修改任何東西。
- 人確認來源後可傳 `accept={"Q3"}`：該項保留在結果中，降為 `warn` 並標示 `accepted`。接受一項不會接受其他項。
- `blocked(findings)` 回傳是否仍有阻擋項。
- **尚未接到自動流程**：Actions 的資料更新 workflow（D2-05、D2-13）目前為還原狀態（PR #48）；恢復時應在 `assemble_package` 前呼叫本關卡，阻擋時不開資料更新 PR 或改為需人工確認。

## 3. 來源失效情境測試（端到端）

每個情境都在「該屆已有一個有效資料包」的狀態下，以真的 runner → 證據儲存 → 品質關卡 → 資料集索引執行：

| 情境 | 狀態 | 錯誤代碼 | 保存的回應 |
|---|---|---|---|
| 403、429 | failed | `access_blocked`（只請求 1 次，不重試、不繞過） | 0 |
| 404 | failed | `http_error` | 0 |
| 500（重試後仍失敗） | failed | `http_error` | 0 |
| 逾時、網路中斷 | failed | `timeout`、`network_error` | 0 |
| 重新導向到允許網域以外 | failed | — | 0 |
| 空回應、欄位改名、非文字內容、HTML 表格消失 | partial | `parse_error` | 1（原樣保存） |
| 只有表頭、名稱全部空白 | **succeeded** | — | 1 |

每個情境都驗證：crawl_run 符合 Schema、證據目錄完整（`verify_run`）、0 筆紀錄；品質關卡阻擋（Q2、Q3；失敗時另有 Q1）；**原有的資料包仍是 `latest_dataset_id`**，`last_acquisition` 記錄這次的狀態（失敗與部分成功附原因），失敗時有 warning 通知；原有資料包的檔案逐位元組不變。

另有資料品質測試：官方筆數高於收集數時報告列出差異與 `partial`、沒有官方筆數時列出缺口、缺網站的企業列為品質旗標（`etl.report`，D2-09）。

## 4. 驗證（2026-11-09，雲端容器，Python 3.11／3.12／3.13）

- `tests/data/test_quality_and_failures.py` 27 個測試全部通過。
- 突變測試 15 個（關閉 Q1–Q5、Q1 不含 cancelled、Q1 降為 warn、Q3 邊界改為 `<=`、`listed` 計入 removed、接受全部／不接受、未知代碼、比例檢查、`blocked`）中 14 個被抓到；1 個為等價突變（`before > 0` 條件），已刪除該多餘條件。

## 5. 不包含

- 把關卡接到 Actions（等 D2-05／D2-13 恢復，需 Albert 決定）。
- 真實來源的失效（sandbox 無法連外；D2-02）。
- 欄位層級的異常偵測（例如攤位格式突然改變）。
