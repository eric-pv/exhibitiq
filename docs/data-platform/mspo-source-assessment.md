# MSPO 資料來源評估

> 工作項目：D1-10｜負責人：data｜調查日期：2026-11-03
> **結論先講：目前無法確認 MSPO 參展商名單能否取得，也無法建立完整度。** 原因不是網站拒絕，而是這次調查所用的工具讀不到主辦單位的名單頁面與 `robots.txt`（見第 1 節）。依 `CLAUDE.md`，這種情況要停下來回報專案負責人，本文件就是回報內容。
> **更新（2026-11-03，Albert 人工確認）：在主辦單位網頁上無法直接看到參展商名單。** 這排除了「名單公開列在網頁上、可以直接擷取」的最樂觀情況，細節與限制見第 4.1 節。

## 0. 這份調查做了什麼、沒做什麼

- 用網頁搜尋與有限的頁面讀取，確認展覽基本資訊、官方公布的數字，以及參展商名單存在的跡象。
- **沒有**打開主辦單位的參展商名單本身，沒有看過它的欄位、筆數、分頁或格式。
- **沒有**讀到 `robots.txt` 與主辦單位的「Regulations and Declarations」（參展規定），所以不知道資料使用條款。
- 沒有對任何網站發出大量請求，也沒有嘗試繞過任何限制。
- 證據等級：**已開啟頁面**（實際讀到頁面內容）、**搜尋摘要**（只看到搜尋結果的片段）。每一項事實都標明。

## 1. 為什麼讀不到

這個雲端工作階段的網頁讀取工具有網址允許清單：`mspo.pl` 與 `targikielce.pl/robots.txt` 不在清單內，被工具拒絕；命令列環境依設定通常也只允許套件庫與 GitHub（我沒有逐一測試）。這是**工具的限制，不是來源網站的回應**。

另一個未知數：日後的爬蟲會在 GitHub Actions 執行，Actions 的對外網路能否連到 `targikielce.pl` 還沒有實測（目前沒有任何 workflow）。

## 2. 已查證的事實

| # | 事實 | 證據與等級 |
|---|---|---|
| F1 | MSPO 2026 是第 34 屆，2026-09-08 至 09-11，地點 Targi Kielce（波蘭凱爾采），主辦單位 Targi Kielce S.A. | 多個獨立來源一致（日本貿易振興機構展覽資料庫、Wikipedia、Defence24 等）；搜尋摘要 |
| F2 | **這一屆已經結束。** 今天（2026-11-03）距閉幕已近兩個月 | 由 F1 與今天日期推得 |
| F3 | 閉幕後的數字：**1,209 家企業、43 個國家**、約 45,000 名參觀者 | Defence24 兩篇閉幕報導（搜尋摘要中只能確認**圖片**署名為 Targi Kielce）；另一網站稱這些是「主辦單位公布」的數字。**數字是否出自主辦單位新聞稿未能確認，尚未打開主辦單位自己的頁面**；搜尋摘要 |
| F4 | 2025 年官方數字是 811 家、35 個國家 | 主辦單位 2026 年手冊 PDF 的標示「data refer to MSPO 2025」；搜尋摘要 |
| F5 | 主辦單位確有「參展商名單」，且附帶會議行事曆功能（B2B 媒合平台的一部分） | 主辦單位網站參展頁；**已開啟頁面** |
| F6 | 參觀者行動 App 內有參展商名單與展位導航 | Defence24 開展前報導；**已開啟頁面** |
| F7 | Defence24 開展前報導有「Lista wystawców」「Rozmieszczenie stoisk」連結，但都是電子報追蹤轉址（`email.targikielce.pl`），最終目的地不明，我沒有追蹤這些轉址 | **已開啟頁面** |
| F8 | 主辦單位的參展申請有「共同參展商（co-exhibitor）網路型錄登錄」，費用含在報名費內 | 2021 年報名表單 PDF 與 2026 年德國薩克森州商務資料；**是舊屆表單與第三方轉述，不是 2026 名單本身**；搜尋摘要 |

## 3. 「參展商數字」有不同口徑

同一屆的數字因來源與口徑而不同，這直接影響完整度判斷。

| 數字 | 來源 | 說明 |
|---|---|---|
| 約 1,000 | 開展前約兩個月的報導 | 報名中的數字 |
| 超過 1,200，另有近 300 家透過夥伴與代表團參與 | 開展當天的產業刊物（Strefa Obrony）；**搜尋摘要中的文字被截斷，無法確認是誰說的** | 暗示「直接參展商」與「被代表的企業」是不同口徑 |
| **1,209** | 閉幕報導（見 F3） | 「firm／wystawców」，是否含被代表的企業**不明** |
| 1,062 | 付費名單販售網站 Expolista（2026-08-21 更新） | 商業來源，不可採用（見第 6 節） |

2024、2025 年也有類似差異：主辦單位 2025 年 811，付費目錄網站 jufair 稱 948；2024 年主辦單位資料 769，jufair 稱 886。日本貿易振興機構資料庫另註明「過去的紀錄可能包含同期或聯合展出」。

**結論：** 專案文件中「約 1,209 筆」的說法，現在有主辦單位閉幕數字的間接支持，但**不能直接當成線上名單的筆數**。線上名單是否含共同參展商、是否涵蓋那近 300 家被代表的企業，都還不知道。

## 4. 參展商名單：已知與未知

**已知：** 名單存在（F5、F6），主辦單位用它做展前媒合。

**未知（都要有人實際打開名單才能回答）：**

1. 最終網址，以及是否需要登入或註冊。
2. 活動結束後名單是否仍然公開；明年屆次開放後是否會被取代或移除。
3. 頁面是靜態 HTML、由 JavaScript 載入，還是背後有 API；有沒有分頁或無限捲動。
4. 總筆數，以及每筆有哪些欄位（名稱、國家、展位、展廳、簡介、網站、聯絡人）。
5. 是否有波蘭文與英文版本，欄位是否一致。
6. 名單是否含個人資料（聯絡人姓名、Email、電話）。若有，只能取公司層級欄位，契約的 `company` 也沒有個人欄位。

### 4.1 人工確認結果（2026-11-03，Albert 回報）

**回報內容：在網頁上無法直接看到參展商名單。**

這個回報**能說明**的事：

- 名單不是以公開頁面直接列出；從網頁入口看不到。這與 F5、F6 一致：主辦單位的說明把名單描述為「B2B 媒合平台」與參觀者 App 的一部分，而不是獨立的公開名錄頁。

這個回報**不能說明**的事（回報中沒有提供）：

- 看的是哪個網址、頁面上有沒有「名單」按鈕、按下去出現什麼（登入、註冊、下載 App，或空白）。
- 名單是「本來就要登入或在 App 內才看得到」，還是「活動結束後已下架」。兩者的處理方式不同，目前**無法區分**。
- 參觀者 App 內現在是否還有名單。

三種可能（**都未證實**）：(a) 名單只在 App 或需註冊的平台內；(b) 活動結束後已下架；(c) 網頁入口有，但需要特定頁面或操作才看得到。

另外：主辦單位的 MSPO 2026 參展條款文件（英文版）存在於加拿大政府招標附件清單中（搜尋摘要），內容我沒有讀到，可作為日後查證資料使用條款的線索。

## 5. 取得限制：已知與未知

**已知：** 沒有任何限制被證實，也沒有任何限制被排除。

**未知：** `robots.txt` 內容、參展規定與網站使用條款中關於資料使用的規定、是否有反爬機制（驗證碼、頻率限制）、名單內容的授權範圍。

依 `CLAUDE.md`：來源被封鎖或完整度無法確認時，停下來問專案負責人；遇到反爬機制時回報，不繞過。

## 6. 不採用的來源

Expolista、ExpoCaptive、jufair、10times 等網站販售或展示 MSPO 參展商名單，部分附決策者姓名與 Email。**不建議使用**：

- 它們是商業轉賣的資料，授權與來源不明，無法對應契約要求的 `source` 追溯。
- 含個人聯絡資料，有個資疑慮。
- 筆數與主辦單位不一致（第 3 節），會污染完整度判斷。

## 7. 風險

| 風險 | 影響 |
|---|---|
| **時間：名單可能在下一屆開放後被取代或移除。** 下一屆（據第三方報導為 2027-08-31 至 09-03，主辦單位日期未查證）的資料可能覆蓋這一屆 | 原始證據一旦消失就無法補抓；越早保存越好（前提是第 5 節的使用條款允許） |
| 完整度口徑不明（直接參展商 vs 含被代表企業） | 無法宣稱 `complete`；`official_exhibitor_count` 填哪個數字需要決定 |
| 名單可能需要登入，或有反爬機制 | 全量取得可能做不到，要改走備案 |
| **網頁上看不到名單（4.1，人工確認）** | 自動擷取公開網頁這條路目前沒有證據可行；若名單只在 App 或登入後才有，自動擷取可能不適當，也可能違反使用條款；真實資料展示（Phase 2）的取得方式要重新決定 |
| Actions 能否連到來源網站未測 | 即使來源可用，自動化也可能被擋 |

## 8. 建議的下一步與需要決定的事

**已完成：** Albert 回報網頁上看不到名單（4.1）。

**還需要 Albert 提供（不需要寫程式）：**

1. 他看的頁面網址，以及頁面上「名單」相關按鈕或文字的原樣內容（例如 `targikielce.pl/en/mspo/exhibit` 的「B2B Matchmaking Platform」區塊、`.../visit/` 的「Map of the exhibition」區塊）；按下去之後出現什麼。
2. `targikielce.pl/robots.txt` 與「Regulations and Declarations」頁面的內容或網址。

我拿到後再更新第 4.1 節，區分 (a)(b)(c) 三種情況。

**需要專案負責人（Eric）決定：**

1. **資料使用立場：** 若使用條款不明確或不允許自動擷取，是否由我們向主辦單位詢問授權／取得匯出檔，還是只做人工保存與匯入（D2-04）。
2. **完整度口徑：** 目標是「直接參展商 1,209」，還是含被代表企業（1,209 加上「近 300」，約 1,500，這是我的推算，不是任何來源的數字）。這決定 `official_exhibitor_count` 與 `completeness_status` 怎麼填。
3. **是否同意先保存快照：** 名單有被取代的風險（第 7 節）；條款確認允許後，盡快保存為不可變的原始證據。

**備案：** D2-04（HTML／PDF／CSV／Excel 匯入轉換）本來就是 MSPO 無法自動擷取時的備案；若名單只能人工取得，Phase 2 改走匯入。

**依 4.1 的建議（不是已查證的事實）：** 在確認名單到底在哪裡、使用條款怎麼寫之前，**不要為 MSPO 開發自動擷取器**（D2-02）。上面第 1 項決定因此更急：若名單只在 App 或登入後才有，最直接的路徑是向主辦單位詢問授權或匯出檔，而不是擷取。

## 9. 對資料契約的影響

- 目前沒有任何可作為 `official_exhibitor_count` 的**已保存來源**。1,209 只是媒體轉述，沒有對應的 `source` 紀錄與 `content_sha256`。依契約 §9，官方筆數沒有來源時必須是 `null`，完整度只能是 `unknown` 或 `partial`，**不得**直接填 1,209。
- 若要使用 1,209，先保存主辦單位自己的閉幕新聞頁作為 `source`（`source_type: official_website`），再填入 `official_count_source_id`。
- 合成測試資料（D1-06）不受影響，仍標示 `data_origin: "synthetic"`。

## 10. 來源（2026-11-03 查詢）

已開啟頁面：

- 主辦單位 MSPO 參展頁：`https://www.targikielce.pl/en/mspo/exhibit`
- Defence24〈Salon MSPO 2026 już od wtorku!〉：`https://defence24.pl/przemysl/salon-mspo-2026-juz-od-wtorku`

搜尋摘要（未開啟全文）：

- Defence24 閉幕報導：`https://defence24.pl/polityka-obronna/co-przynioslo-mspo-2026-kontrakty-premiery-i-wspolpraca-z-zagranica`、`https://defence24.pl/przemysl/rekordowe-mspo-2026-cztery-dni-ktore-potwierdzily-pozycje-kielc-jako-jednego-z-najwazniejszych-centrow-swiatowego-przemyslu-obronnego`
- 主辦單位 2026 年手冊（含 2025 年數字；英文與波蘭文版一致）：`https://www.targikielce.pl/mspo-2026-folder-en.pdf`、`https://www.targikielce.pl/mspo-2026-folder-pl.pdf`
- 主辦單位 MSPO 參觀頁：`https://www.targikielce.pl/en/mspo/visit/`
- 加拿大政府招標附件清單（列有主辦單位 MSPO 2026 參展條款文件，內容未讀）：`https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-100-54125791`
- 日本貿易振興機構展覽資料庫：`https://www.jetro.go.jp/en/database/j-messe/tradefair/detail/159998`、`https://www.jetro.go.jp/en/database/j-messe/tradefair/detail/152681`（含 2024 年數字）、`https://www.jetro.go.jp/en/database/j-messe/tradefair/detail/135329`（含 2023 年數字）
- Wikipedia：`https://en.wikipedia.org/wiki/MSPO`
- Strefa Obrony 開展當天刊物：`https://fliphtml5.com/evzxj/bpoe/10/`
- 2021 年共同參展商登錄表單：`https://www.targikielce.pl/storage/file/core_files/2021/3/24/d5e4b5b6857ebbcf2ced6c7eeab7812b/mspo-2021-ang-USD-form-8c.pdf`
- 德國薩克森州 MSPO 2026 資料：`https://standort-sachsen.de/fileadmin/user_upload/Veranstaltungen/WFS/Downloads/MSPO_Factsheet_2026.pdf`
- 第三方（僅用於比較口徑，不採用）：`https://www.expolista.com/tradeshows/mspo/2026`、`https://en.jufair.com/exhibition/mspo/periodical`
