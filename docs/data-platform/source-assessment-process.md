# 通用的展覽來源探索與可行性評估流程

> 工作項目：D1-11｜負責人：data｜範本：[`source-assessment-template.md`](source-assessment-template.md)
> 依據：總規範 §1.1（通用性）、`CLAUDE.md` V2.3 強制規則、`docs/specs/dataset-index-contract.md`（`acquisition`、`last_acquisition`）。
> **本流程不針對任何特定展覽。** 任何展覽都用同一套步驟評估；評估結果決定怎麼取得資料，不是預設答案。**不得假設一個展覽一定能全自動取得。**

## 1. 目的

新增一個展覽時，先回答：**官方有哪些資料來源？能不能合法取得？用什麼方式取得？能不能確認取得的資料完整？** 結果寫成一份評估報告，並對應到資料集索引的 `acquisition` 欄位，讓 Dashboard 顯示每個展覽的取得方式與限制（MVP 驗收 V3）。

評估失敗（例如沒有公開名單、需要授權）是**有效的結果**：記錄原因，改用其他方式或其他展覽，**不得阻礙通用系統繼續開發**（V2.3）。

## 2. 輸入與輸出

| | 內容 |
|---|---|
| **輸入** | 展覽名稱、國家、官方網站、要處理的年份（來自展覽登錄；登錄契約見 A1-10）。只有這些，**不含**任何來源事實 |
| **輸出 1：評估報告** | 依[範本](source-assessment-template.md)填寫，存放在 `docs/data-platform/<exhibition_id>-source-assessment.md`（沿用資料集索引契約 §3 的路徑慣例）|
| **輸出 2：索引欄位** | `acquisition.method`、`acquisition.status`、`acquisition.assessed_at`、`acquisition.report_path`、`acquisition.notes`（由資料集索引產生程式 D2-12 寫入 `data/index/datasets.json`；本流程只決定值）|
| **輸出 3：來源設定草稿** | 取得方式為 `automatic` 時，附上符合 D1-07 `SourceConfig` 的設定（見第 6 節）|

## 3. 步驟

### 步驟 0：前置
- 確認這個展覽已登錄且狀態為已接受；評估範圍是「一個展覽 × 要處理的年份」。
- 不要因為主辦單位、國家或過去的經驗，預設任何結論。

### 步驟 1：探索官方來源
從官方網站出發，找出所有**官方**可能的資料來源，逐一列入候選來源表：

- 參展商名單、線上型錄、展位平面圖、參觀者 App 內的名單
- 展覽手冊、型錄 PDF、新聞稿、官方統計（官方筆數的來源）
- 可下載的檔案（CSV、Excel、PDF）
- 展覽官方的 API 或資料頁

**第三方來源只當線索，不當資料來源**：商業名單販售網站、聚合網站、新聞轉述。原因：授權與來源不明、常含個人聯絡資料、筆數口徑常與官方不同，且無法對應契約要求的 `source` 追溯。

來源種類使用契約 `source.source_type` 的值：`official_exhibitor_list`、`official_website`、`official_document`、`exhibitor_website`、`press_release`、`pdf_import`、`csv_import`、`excel_import`、`manual_entry`、`other`。

### 步驟 2：逐一評估候選來源
每個候選來源回答下列問題（範本中有對應表格）：

| 面向 | 要確認的事 |
|---|---|
| 可存取性 | 公開、需登入或註冊、只在 App 內、已下架？ |
| 格式與結構 | 靜態 HTML、由 JavaScript 載入、背後有 API、檔案？有沒有分頁或無限捲動？ |
| 內容 | 有哪些欄位？語言？有沒有個人資料（聯絡人姓名、Email、電話）？ |
| 規模線索 | 頁面或官方文件有沒有公布參展商總數？口徑是什麼（直接參展商、含共同參展商、含被代表企業）？ |
| 使用條款 | `robots.txt`、網站使用條款、參展規定、授權聲明各怎麼說？ |
| 防護機制 | 驗證碼、頻率限制、反爬？ |
| 穩定性 | 活動結束後是否會被下架或被下一屆取代？ |

### 步驟 3：評估完整度可行性
- 能否取得**官方公布的參展商數**，且該數字**有可保存的來源**？可以 → 日後才有機會判定 `complete`。
- 不能 → 完整度只會是 `unknown` 或 `partial`；**不得用估計值、媒體轉述或歷史討論數字填入**（資料包契約 §9）。
- 不同口徑的數字要分別記下口徑，不得混用。

### 步驟 4：結論與取得方式
依第 5 節的對應表決定 `method` 與 `status`，並寫明限制與失敗原因。

### 步驟 5：記錄
- 評估報告存檔（第 2 節路徑）。
- 取得失敗另記在 `last_acquisition`（`status: "failed"` 必須有 `notes`，且不得有 `dataset_id`；失敗不會產生資料包）。
- 實際擷取失敗時，用 D1-07 的錯誤格式（`access_blocked`、`timeout`、`parse_error` 等）記錄，詳見 [`run-logging-and-errors.md`](run-logging-and-errors.md)。

### 步驟 6：何時要問專案負責人
只針對**這個展覽的下一步**，下列情況停下來請專案負責人決定；**其他展覽與工作照常進行**：

- 來源被封鎖（驗證碼、403、頻率限制）：回報，**不繞過**。
- 使用條款不明確，或禁止自動擷取，但仍想取得。
- 需要向主辦單位取得授權或檔案。
- 無法確認完整度，卻需要對外宣稱完整。
- 需要新的 Schema 欄位（依 `schemas/VERSIONING.md` §5 開 `[schema]` Issue）。

### 步驟 7：取得資料時
- 條款確認允許後，**盡快保存原始快照**作為不可變的原始證據（來源可能被下架或被下一屆取代）。
- 取得速率先用保守預設，並遵守來源的限制。
- 只取**公司層級**欄位；個人聯絡資料不進資料包。

## 4. 證據規則

評估只能陳述有證據的事。每項結論標明證據等級：

| 等級 | 意義 |
|---|---|
| **已開啟頁面** | 實際讀到頁面或檔案內容 |
| **搜尋摘要** | 只看到搜尋結果的片段，沒有開啟全文 |
| **人工回報** | 使用者（人）回報，未附網址或內容，原因與細節無法判斷 |
| **未存取** | 沒有讀到（例如工具或網路限制） |

- **工具讀不到，不等於來源拒絕。** 要分清「我的工具讀不到」與「來源回應拒絕」。
- 「未存取」的項目（例如沒讀到 `robots.txt`）要明寫為**未知**，不得推測為允許或禁止。
- 數字要連同口徑與出處一起記；沒有出處的數字不寫。

## 5. 結論對應表

`method`、`status` 的值來自資料集索引契約，**不得自創**。下表是本流程如何選擇：

| 評估結果 | `method` | `status` | `notes` |
|---|---|---|---|
| 公開頁面可以直接擷取，條款允許，結構穩定 | `automatic` | `feasible` | 選填 |
| 公開，但需要人工步驟才能完成（例如先登入下載、分段操作） | `semi_automatic` | `feasible` 或 `partially_feasible` | 說明人工步驟 |
| 公開的 PDF、CSV、Excel 可下載 | `file_import` | `feasible` | 選填 |
| 只能取得部分資料（部分欄位、部分年份、需大量人工） | 實際可用的方式：`automatic`、`semi_automatic`、`file_import` 或 `manual_entry` 之一 | `partially_feasible` | **必填**，說明缺什麼 |
| 需要主辦單位或權利人授權或提供檔案 | `authorized_file` | `pending_authorization` | **必填**，說明需要什麼授權 |
| 只能人工輸入 | `manual_entry` | `partially_feasible` | **必填** |
| 沒有合法可行的取得方式（名單不公開、條款禁止、需登入且不可自動） | `undetermined` | `not_feasible` | **必填**，說明原因（Dashboard 會顯示）|
| 尚未評估 | `undetermined` | `not_assessed` | — |

`status` 不是 `not_assessed` 時，`assessed_at`（UTC）與 `report_path` 必填。

`status` 說的是**能不能取得**；**資料是否完整**是另一件事，由資料包的 `completeness_status` 表達（步驟 3）。

## 6. 來源設定草稿（`automatic` 時）

評估為 `automatic` 時，在報告附上來源設定，格式即 D1-07 的 `SourceConfig`（TOML）。下面是**合成範例**（保留網域，不是任何真實來源）：

```toml
name = "example-source"
exhibition_id = "example-expo"
edition_id = "example-expo-2026"
source_type = "official_exhibitor_list"
start_urls = ["https://www.example.com/exhibitors"]
allowed_domains = ["example.com"]
rate_limit_per_second = 0.5
max_retries = 2
timeout_seconds = 30
```

設定檔不放帳密、Token 或任何機密；網址不得內嵌帳密。`rate_limit_per_second` 要依步驟 2 查到的來源限制設定，沒有查到時用保守值，不要假設允許更快。

## 7. 與其他工作項目的關係

| | 關係 |
|---|---|
| A1-10 展覽登錄 | 提供輸入（名稱、國家、官網、年份）。登錄資料不含來源事實 |
| D1-07 來源設定與錯誤格式 | 第 6 節的設定、步驟 5 的錯誤代碼 |
| D2-02 通用網站擷取、D2-04 匯入轉換 | 依本流程的結論選擇取得方式 |
| D2-12 資料集索引 | 把結論寫成 `acquisition`，把取得結果寫成 `last_acquisition` |
| D2-13 新增展覽 workflow | 產生登錄草稿與評估報告草稿，輸出為資料更新 PR |

## 8. 已知限制

- 這是**文件流程**，評估本身需要人（或有網路存取的工作階段）實際查證；本流程不自動評估。
- 工具的網路存取可能受限（例如網址允許清單），讀不到時只能標為「未存取」，要靠人工補查。
- 結論對應表（第 5 節）是資料工程的流程規則；欄位值本身由 Schema 與契約定義，若契約改變，要同步修改本文件，由測試比對。
