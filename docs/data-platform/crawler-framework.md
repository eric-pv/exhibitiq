# 共用爬蟲框架與來源註冊機制

> 工作項目：D2-01｜負責人：data｜程式：`crawler/{models,adapters,sources,clock,fetch,robots,runner}.py`、`etl/ids.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 設計原則（V2.3）

- 框架只處理**所有來源共通**的事：頻率限制、重試與退避、網域範圍、robots.txt、SSRF 防護、錯誤分類、來源證據（provenance）、日誌。
- 展覽之間的差異只放在兩處：**來源設定**（TOML）與**適配器**（`SourceAdapter` 子類）。新增展覽 = 新增設定，最多再加一個適配器，**不修改框架**。
- 適配器不得寫死展覽名稱、ID 或 URL；框架程式也不得（`test_no_hardcoded_exhibition.py` 會檢查）。
- 取得失敗是資料，不是例外：每個失敗都變成結構化錯誤，進日誌與 `crawl_run`；一個來源失敗不影響其他來源。

## 2. 元件

| 模組 | 內容 |
|---|---|
| `crawler/models.py` | `Request`、`Response`、`Snapshot`（原始位元組＋出處）、`ExtractedRecord`、`ParseResult` |
| `crawler/adapters.py` | `SourceAdapter`（`parse()` 必填；`start_requests()`、`validate_options()` 可覆寫）、`AdapterRegistry`、`resolve_adapter` |
| `crawler/sources.py` | `SourceRegistry`：載入目錄內全部來源設定，一次回報所有錯誤 |
| `crawler/fetch.py` | `Fetcher` 介面與標準函式庫實作 `UrllibFetcher`（無額外相依） |
| `crawler/robots.py` | robots.txt 判讀 |
| `crawler/runner.py` | `run_source`、`run_all`、`RunOptions`、`RunResult` |
| `crawler/clock.py` | `Clock` 介面；測試用假時鐘，不真的等待 |
| `etl/ids.py` | `new_ulid`、`make_id`：產生 `src_`、`run_` 等 ID（符合 `common.schema.json`） |

來源設定新增兩個選填欄位：`adapter`（適配器名稱，`^[a-z][a-z0-9_-]{0,63}$`）與 `[options]` 表（交給適配器；設定檔不得含 token、密碼、金鑰類欄位名稱，含巢狀表與陣列內的表）。

## 3. 每個來源都套用的規則

| 項目 | 行為 |
|---|---|
| 範圍 | 只抓 `allowed_domains` 內的 `http(s)`；請求前檢查、**每次重新導向再檢查**、回應後再檢查最終 URL |
| 內部網路 | 預設拒絕解析到非公開位址（loopback、私有、link-local 含雲端 metadata、保留位址）；一個位址不合格即拒絕 |
| 憑證 | 拒絕 `Authorization`、`Cookie`、`Proxy-Authorization` 標頭與網址內嵌帳密；登入不是取得方式 |
| 回應 | `Accept-Encoding: identity`（不處理壓縮）、大小上限 `max_bytes`（超過即錯誤，不截斷） |
| 頻率 | 每秒不超過 `rate_limit_per_second`（重試與 robots.txt 也算），且不低於網站 `Crawl-delay`（上限 `max_crawl_delay_seconds`） |
| robots.txt | 預設遵守，每個 origin 取一次。2xx → 套用規則；404/410 等 4xx → 視為沒有；**401/403/429、5xx、逾時、網路錯誤 → 視為全部禁止** |
| 重試 | 只重試可能暫時的錯誤（逾時、網路錯誤、5xx、408），最多 `max_retries` 次，指數退避 `min(backoff_max, base × 2^(n-1))` |
| 被封鎖 | **401/403/429 立即停止該來源**：不重試、不換標頭、不繞過；記錄 `access_blocked` |
| 證據 | 每個成功回應先存成 `Snapshot`（原始位元組、`sha256:`、`retrieved_at`、新 `src_` ID）**再**解析；解析失敗不會遺失證據 |
| 解析失敗 | `ParseError` → `parse_error`；其他例外 → `unexpected`；不中止、不保留該頁半成品紀錄 |
| 去重 | 去除 fragment、統一 scheme 與主機大小寫；每個 URL 只抓一次 |
| 上限 | `max_requests` 限制頁面請求數；超過則截斷、標 `partial` 並在 `notes` 寫明資料不完整 |

## 4. 執行狀態

`crawl_run.status`：

| 狀態 | 條件 |
|---|---|
| `cancelled` | 呼叫端要求停止（保留已收集內容） |
| `failed` | 沒有取得任何頁面（robots.txt 不算） |
| `partial` | 有取得頁面，但發生過任何錯誤或被截斷 |
| `succeeded` | 無錯誤、未截斷 |

`stats.requests_*` 計算所有 HTTP 嘗試（含 robots.txt 與重試）；`records_extracted` 為適配器回傳的紀錄數。被 robots.txt 禁止的 URL 記為 `access_blocked` 錯誤（未請求）。

## 5. 多來源執行

`run_all(configs, adapters=…, fetcher=…)` 逐一執行，**單一來源的設定錯誤、找不到適配器、被封鎖或框架崩潰，只會產生該來源的 `failed` 結果，不影響其他來源**（V2.3：單一展覽取得失敗不得阻礙通用系統）。

## 6. 寫一個適配器

```python
from crawler.adapters import default_registry, SourceAdapter, ParseError
from crawler.models import ParseResult, Request

@default_registry.register
class MyListAdapter(SourceAdapter):
    name = "my-list"
    version = "0.1.0"

    def parse(self, response, request, config):
        # 只做解析，不做 I/O；回傳「如原文所列」的原始欄位，欄位對應由 ETL（D2-07）處理
        rows = [...]
        if not rows:
            raise ParseError("exhibitor table not found")
        return ParseResult(records=rows, follow=[Request(next_url)])
```

## 7. 已知限制與不包含

- 僅 `GET`；無 JavaScript 渲染、無登入、無 CAPTCHA 處理（遇到即屬 `access_blocked` 或需人工）。
- 名稱解析先檢查再連線（DNS rebinding 未涵蓋）；若設定 HTTP proxy，名稱由 proxy 解析（同樣未涵蓋）。`allow_private_networks=True` 只供測試。
- 快照**不落地**：`SnapshotSink` 只是介面，保存到 Git/Release 屬 D2-06。
- 不做欄位對應、正規化、去重（D2-07、D2-08 之後）；不含內建適配器（D2-02、D2-04）與 GitHub Actions workflow（D2-13）。
- 同一來源內為循序執行；不平行抓取（刻意保守）。
