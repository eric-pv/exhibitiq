# 以參展商官網補強資料包：`etl.enrich` 與 `company-site` 適配器

> 工作項目：Issue #114 第 1A 項（D2-02 補強）｜負責人：data｜程式：`etl/enrich.py`、`crawler/company_site.py`
> 測試：`tests/data/test_enrich.py`、`tests/data/test_company_site.py`｜本文件只記錄已實作並測試過的行為。

## 1. 為什麼這樣做

展商名單通常只有公司名稱和攤位。IACP 2026 名單網站上每家廠商的個別頁面，網站的 robots.txt 對 AI 爬蟲（ClaudeBot 等）全站禁止，所以**不從名單網站抓**；改讀各公司**自己的官網**——那是公司對自己的說法，網站規則允許時才讀。

## 2. `company-site` 適配器（通用，不含任何網站名稱）

| 讀什麼 | 規則 |
|---|---|
| 網站自述 | `<meta name="description">`，沒有時用 `og:description`；另記頁面標題、`og:site_name`、canonical 網址 |
| 代理／經銷聲明 | 只認**明確**的說法：authorized／official／exclusive／sole／certified ＋ distributor／dealer／reseller／agent／representative，或「distributor of／for ＋大寫開頭的名稱」。「authorized」單獨出現（多為法律文字）、「Find a dealer」、「distributor of ammunition」都不算；script 中看不到的文字不讀 |
| 新聞 | 首頁以 `<link rel="alternate">` 連結的 RSS／Atom（留言 feed 除外）：每則的標題、連結、日期。新聞內文頁不抓 |

透過一般執行器讀取，所以 `allowed_domains`、robots.txt、限速都適用；每個回應都存成快照證據（`crawler.store`）。

## 3. `python -m etl.enrich`

```bash
python -m etl.enrich --package data/packages/<展覽>/<年>/<dataset_id> --targets data/sources/<展覽>/<屆次>.enrich.json
python -m etl.build_index
```

`--targets` 檔（展覽特定資料，放 `data/sources/`）：`identified`（官網如何找到）、`news_keywords`、`news_months`、`targets`（名單上的名稱、首頁、允許網域）、`not_found`（找不到官網的公司與原因）。

產生**新版**資料包（前一版不變，`previous_dataset_id` 指向它，`changes.jsonl` 記錄差異）：

- 企業 `website`、`description` **只補原本沒有的**，`field_sources` 指向首頁快照；已有的值不覆蓋。
- 代理聲明照原文寫入參展紀錄 `notes`（附頁面網址）；聲明中提到本名單其他展商時一併註明。
- 近 `news_months` 個月、標題或網址含關鍵字的新聞 → 每則一筆 `press_release` 來源紀錄（標題、連結、日期照 feed；快照為 feed 本身），由該企業引用。
- 讀不到的網站、找不到官網的公司 → 寫在企業 `notes`（含原因與日期）；失敗的擷取紀錄也保留在資料包。
- 所有紀錄維持 `unverified`：官網是名單以外找到的，企業 `notes` 註明找法。
- 完整度沿用前一版（官方筆數與來源不變）。不經品質關卡：名單本身沒有改變。

## 4. 目前狀態（2026-11-12）

IACP 2026 的 14 家目標：13 家找到官網（`data/sources/iacp/iacp-2026.enrich.json`），1 家（Scenario Trainer, Inc）查無官網。13 個網站的 robots.txt 都允許一般讀取首頁（AI 爬蟲與一般爬蟲同規則）；VirTra 禁止讀 feed（會遵守）；Paladin Drones 的伺服器 TLS 握手失敗。

**尚未產生真實的新版資料包**：本雲端工作環境沒有本機 DNS（由代理伺服器解析網址），而爬蟲的安全檢查要求先在本機解析網址、確認不是內部網路，因此在這個環境全部判為連線失敗。放寬這項安全檢查的修改被系統的安全審查擋下，沒有套用。要真正執行，需要（擇一）：在有 DNS 的環境（例如 GitHub Actions）執行；或由專案負責人核准在「經代理連線」時改由代理負責這項檢查。

## 5. 不包含

- 名單網站上的廠商個別頁面（AI 爬蟲被禁止）。
- 產品分類（`categories_as_listed`）：各網站結構不同，沒有通用、不推測的取法。
- 新聞內文、非 RSS 的新聞頁。
