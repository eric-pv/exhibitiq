# 來源設定、錯誤格式與執行日誌

> 工作項目：D1-07｜負責人：data｜程式：`crawler/source_config.py`、`crawler/errors.py`、`crawler/runlog.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 為什麼分成三塊

| 模組 | 回答的問題 | 是否屬於共用契約 |
|---|---|---|
| `source_config` | 抓什麼、抓得多客氣？ | 否，爬蟲內部設定 |
| `errors` | 出錯時怎麼描述？ | 只有 `code`、`message`、`url`、`occurred_at` 會進 `crawl_run.error_samples` |
| `runlog` | 執行過程怎麼記？ | 事件日誌否（契約允許資料工程自訂）；`crawl_run` 紀錄是，依 `schemas/v1/crawl_run.schema.json` |

`exhibition_id`、`edition_id`、`source_type` 的合法值由契約擁有。設定檔只把它們當字串保存，不複製規則；打包時由資料包驗證程式（D1-05）檢查。

## 2. 來源設定（TOML）

```toml
name = "example-crawler"
exhibition_id = "example-expo"
edition_id = "example-expo-2026"
source_type = "official_exhibitor_list"
start_urls = ["https://www.example.com/exhibitors"]
allowed_domains = ["example.com"]
# 以下選填，預設值如下
rate_limit_per_second = 1.0
max_retries = 3
timeout_seconds = 30
user_agent = "ExhibitIQ-crawler"
```

`load_source_config(path)` 會拒絕：

- 未知的鍵（防止拼字錯誤被默默忽略）。
- 看起來像機密的鍵（名稱含 token、secret、password、api_key、credential）：機密不得放進 Git。
- 非 http(s) 的網址、網址內嵌帳密、網址主機不在 `allowed_domains`（含主機只是名稱後綴相同，例如 `notexample.com`）。
- `allowed_domains` 不是單純網域名稱（含協定、路徑，或沒有點的名稱如 `localhost`）。
- `max_retries` 不是 ≥ 0 的整數；`rate_limit_per_second`、`timeout_seconds` 不是 > 0 的數字（布林值不算數字）。

錯誤訊息一律包含檔案路徑。設定物件是不可變的。預設限速 1 次／秒是保守預設，不是對任何來源允許速率的判斷；實際來源的限制要在 D1-10 查證後設定。

## 3. 錯誤格式

`CrawlError(code, message, url, occurred_at, http_status, retryable)`。

| `code` | 預設可重試 | 用於 |
|---|---|---|
| `config_invalid` | 否 | 設定錯誤 |
| `network_error` | 是 | 連線失敗 |
| `timeout` | 是 | 逾時 |
| `http_error` | 否 | 非預期的 HTTP 狀態 |
| `access_blocked` | 否 | 403／429、驗證碼、反爬機制：停止並回報，不繞過 |
| `parse_error` | 否 | 內容無法解析 |
| `unexpected` | 否 | 其他 |

- `to_error_sample()` 只輸出契約允許的四個欄位，未提供的欄位**省略**而不是填 `null`。
- `http_status`、`retryable` 只進事件日誌，因為契約的 `error_samples` 項目不允許額外欄位。
- `message` 不可為空白。

## 4. 執行日誌

### 事件日誌（JSONL）

每行一個 JSON 物件，鍵排序、UTF-8（不跳脫中文）、以 `\n` 結尾：

```json
{"event":"request","http_status":500,"level":"WARNING","succeeded":false,"ts":"2026-11-03T06:00:01Z","url":"https://www.example.com/b"}
```

固定欄位：`ts`（UTC，結尾 `Z`）、`level`（`DEBUG`／`INFO`／`WARNING`／`ERROR`）、`event`；`message` 選填。自訂欄位不可與這四個同名。

內建事件：`request`（成功為 INFO，失敗為 WARNING）、`records_extracted`、`error`（ERROR）。`RunLog(stream)` 寫入任何文字串流（檔案或 stdout，GitHub Actions 日誌可直接看到），時間來源可注入，所以測試輸出是確定性的。

### `crawl_run` 紀錄

`RunLog` 累計 `requests_attempted`、`requests_succeeded`、`records_extracted`、`error_count`；錯誤樣本最多保留 50 筆（契約上限），超過後 `error_count` 仍繼續累計。`build_crawl_run(...)` 組出符合契約的紀錄：

- 選填欄位（`code_commit`、`github_run_url`、`notes`）與沒有錯誤時的 `error_samples` 一律**省略**。
- `status` 由呼叫端指定，程式不推測什麼算 `succeeded` 或 `partial`。
- 只記錄已結束的批次，所以 `finished_at` 與 `status` 必填。

## 5. 驗證結果

測試用本機 `schemas/v1/crawl_run.schema.json`（含 `$ref` 到 `common.schema.json`）驗證產生的紀錄：有錯誤與選填欄位、沒有錯誤兩種情況都通過；錯誤樣本滿 50 筆仍通過；故意給不合法的 `status` 會失敗（確認測試不是空轉）。

## 6. 不包含

- **ID 產生**：`crawl_run_id` 由呼叫端提供（契約：擷取批次開始時指派）。ULID 產生器等到真正需要的工作項目再做。
- 網路請求、重試與限速的**執行**：本模組只定義設定與記錄格式，框架屬 D2-01。
- 事件日誌的 Schema：日誌格式只在本文件定義，不放進 `schemas/`；若 Dashboard 系統狀態頁需要讀取日誌，要先請專案負責人定義契約。
- ETL 端的日誌：目前只在 `crawler/`；ETL 需要時再抽成共用，避免現在猜錯介面。
- 測試中的 `crawl_run` 驗證用了一個很小的本機 Schema 註冊工具，只存在於 `tests/data/test_runlog.py`。專案唯一的資料包驗證程式是 D1-05。
