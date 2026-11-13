# 展覽來源評估報告：`<exhibition_id>`（`<年份>`）

> 範本：複製本檔到 `docs/data-platform/<exhibition_id>-source-assessment.md` 後填寫，刪掉這段說明與所有 `（說明）` 括號。
> 流程見 [`source-assessment-process.md`](source-assessment-process.md)。**只寫有證據的事；沒讀到的寫「未知」。**
> 證據等級：**已開啟頁面**／**搜尋摘要**／**人工回報**／**未存取**（定義見流程第 4 節）。

## 1. 基本資訊

| 欄位 | 內容 |
|---|---|
| 展覽名稱 | |
| `exhibition_id` | |
| 國家 | |
| 官方網站 | |
| 要處理的年份 | |
| 評估日期（UTC） | |
| 評估者 | （人或工作階段） |
| 登錄狀態 | （已接受） |

## 2. 結論（對應資料集索引 `acquisition`）

| 欄位 | 值 |
|---|---|
| `method` | （`automatic`／`semi_automatic`／`file_import`／`authorized_file`／`manual_entry`／`undetermined`）|
| `status` | （`feasible`／`partially_feasible`／`not_feasible`／`pending_authorization`／`not_assessed`）|
| `assessed_at` | （UTC，`status` 不是 `not_assessed` 時必填） |
| `report_path` | `docs/data-platform/<exhibition_id>-source-assessment.md` |
| `notes` | （`partially_feasible`、`not_feasible`、`pending_authorization` 時必填，說明原因） |

**一句話結論：**（例：官方名單是公開 HTML，條款允許，可自動取得；官方筆數有來源。）

## 3. 候選來源

| # | 來源 | 網址 | `source_type` | 可存取性 | 證據等級 |
|---|---|---|---|---|---|
| 1 | | | | （公開／需登入／App 內／已下架／未知） | |

第三方來源只列為「線索」，不列入上表。線索：

- （來源、為什麼不採用）

## 4. 各來源評估

每個候選來源複製一份。

### 來源 1：（名稱）

| 面向 | 發現 | 證據等級 |
|---|---|---|
| 可存取性 | | |
| 格式與結構（HTML／JS／API／檔案；分頁） | | |
| 欄位與語言 | | |
| 個人資料（有／無／未知） | | |
| 規模線索（總數與口徑） | | |
| 防護機制（驗證碼／頻率限制） | | |
| 穩定性（會不會被下架或取代） | | |

## 5. 使用條款與限制

| 項目 | 發現 | 證據等級 |
|---|---|---|
| `robots.txt` | （內容摘要；沒讀到寫「未知」） | |
| 網站使用條款 | | |
| 參展規定或授權聲明 | | |
| 資料使用限制（再散布、自動擷取、商業使用） | | |

## 6. 完整度可行性

| 項目 | 內容 |
|---|---|
| 官方公布的參展商數 | （數字；沒有寫「未知」）|
| 該數字的口徑 | （直接參展商／含共同參展商／含被代表企業／未知）|
| 該數字的來源與證據等級 | （必須是可保存的官方來源，否則不得填入資料包）|
| 預期的 `completeness_status` | （`complete`／`partial`／`unknown`，並說明理由）|

不得用估計值、媒體轉述或歷史討論數字當作官方筆數。

## 7. 取得方式決策與理由

（依流程第 5 節的對應表說明為什麼選這個 `method` 與 `status`；列出考慮過但不採用的方式。）

## 8. 失敗與限制

| 項目 | 內容 |
|---|---|
| 失敗原因代碼 | （`access_blocked`／`timeout`／`network_error`／`http_error`／`parse_error`／`config_invalid`／`unexpected`；沒有失敗寫「無」）|
| 失敗說明 | |
| 已知限制 | |
| 這個失敗是否影響其他展覽 | （依 V2.3 不得阻礙；請寫「不影響」或說明如何隔離）|

## 9. 建議的來源設定（取得方式為 `automatic` 時）

```toml
name = ""
exhibition_id = ""
edition_id = ""
source_type = ""
start_urls = []
allowed_domains = []
```

## 10. 未解事項與需要決定的事

| 事項 | 需要誰決定 | 備註 |
|---|---|---|
| | （專案負責人／主辦單位授權／無） | |

## 11. 來源清單

（所有實際開啟或搜尋到的網址，標明證據等級與查詢日期。）
