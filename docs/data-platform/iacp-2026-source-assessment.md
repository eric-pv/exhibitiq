# 展覽來源評估報告：`iacp`（`2026`）

> 依 `source-assessment-template.md`。評估日 2026-11-09，評估者：data（Albert 的 Claude Code）。
> 本報告只記錄實際查到的內容；未查證的事項列在 §10。這份來源是**由人挑選並提供的檔案**，不是 V2.3 意義下的「指定測試展覽」；它取得失敗或被撤下，不會阻礙通用系統。

## 1. 基本資訊

| 項目 | 內容（來源） |
|---|---|
| exhibition_id／edition_id | `iacp`／`iacp-2026` |
| 名稱 | IACP 2026 Conference & Exhibition（PDF 標題與頁尾） |
| 日期、地點 | Oct. 24–27、Orlando, FL（PDF 頁首）→ `2026-10-24`～`2026-10-27`、Orlando、US |
| 展商名單頁 | `https://iacp2026.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm?featured=false` |
| 官方展商數 | 662（同頁標題「All Exhibitors (662)」） |

## 2. 結論（資料集索引 `acquisition`）

- `method: file_import`、`status: partially_feasible`。
- **自動擷取：不可行**（§5）。**人工列印 PDF 後匯入：可行**，662／662 筆，`completeness_status: complete`。

## 3–4. 候選來源與評估

| 來源 | 結果 |
|---|---|
| 展商名單頁（網站擷取） | 不擷取。頁面本身未被 robots.txt 禁止，但名單資料由 `/8_0/ajax` 動態載入（對所有爬蟲禁止），且需執行 JavaScript（框架不支援，刻意） |
| 同頁由人用瀏覽器「另存 PDF」（Edge 156，2026-11-09T07:05:46Z） | 採用。100 頁，前 67 頁有文字層；含 Featured（59，為全部名單的子集）與 All Exhibitors（662）兩段。只讀 All Exhibitors |

## 5. 使用條款與限制

- `robots.txt`（2026-11-09 取得，sha256 `05fbb7d4052624c15357e5455e34b2c1818f540db1048125d3f406c18481d801`）：`User-agent: *` 禁止 `/8_0/ajax`、`/8_0/cfc` 等；**對 ClaudeBot、Claude-SearchBot、GPTBot、PerplexityBot、meta-externalagent 等 AI 爬蟲 `Disallow: /`**。
- 因此本專案**沒有**以爬蟲存取該網站（只讀過 robots.txt 一次）。檔案由人在瀏覽器取得後提供。
- 網站方對 AI 用途的意向是上述 robots.txt；以此檔案做 AI 分析並放在公開 repo，屬專案負責人／Albert 的決定（CLAUDE.md：開發期間真實展覽資料可暫時提交公開 repo，Eric 2026-11-05）。使用條款頁面未查閱（§10）。
- 名單內容只有公司名稱與攤位號，沒有個人資料。

## 6. 完整度

標題宣稱 662，讀到 662，名稱無重複、全部有攤位號。8 個長名稱在 PDF 文字層換行，已跨行比對。抽查第 1–3 頁與第 41 頁，與畫面一致。

## 7. 取得方式與理由

`printed-listing` 適配器（`crawler/printed_listing.py`，通用：不含任何網站名稱）＋來源設定 `data/sources/iacp/iacp-2026.toml`（段落標題、頁首頁尾要忽略的行）＋展覽資料 `data/sources/iacp/iacp-2026.info.json`；以 `python -m etl.import_file` 匯入。

## 8. 失敗與限制

- 無法自動更新；要更新需由人重新列印。
- 只有名稱與攤位；沒有國家、網站、分類、產品（PDF 列表模式不顯示）。企業詳情頁未取得。
- 攤位欄保留原文，包含「Client Suite #141 ON HOLD」「Hold NCIS」等主辦方標註。

## 9. 建議的來源設定

不適用（取得方式不是 `automatic`）。

## 10. 未解事項

- 網站使用條款未查閱；是否向主辦單位（IACP）取得授權檔案（`authorized_file`）由 Albert 決定。
- 公開 repo 是否保留此真實名單：專案負責人決定。

## 11. 來源清單

| source_id | 內容 | 保存 |
|---|---|---|
| `src_01M6ZJD6J156M8XCRREP6CTAWJ` | 列印的 PDF（3,723,143 bytes） | Git：`data/raw/iacp/iacp-2026/run_01M6ZJD6HZTDMBQ7R4GPET5RQA/snapshots/` |
