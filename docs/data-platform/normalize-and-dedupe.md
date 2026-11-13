# 清洗、標準化、企業去重與別名關聯

> 工作項目：D2-07｜負責人：data｜程式：`etl/normalize.py`、`etl/registry.py`、`etl/build_records.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 原則

1. **不發明資料。** 缺的欄位維持缺；無法標準化的值丟棄並在報告留警告，原文留在 `*_as_listed`。
2. **身分由登錄表決定，不由名稱推導。** `company_id` 是隨機 ULID（契約 §2），指派後永不變更、不重用。
3. **保守比對。** 只有「完全相同的名稱鍵」且「國家沒有矛盾」才視為同一家。名稱相似、法律型態不同、網站相同，一律只列為**候選**給人判斷，**不合併**（契約：相似不代表同一家；合併由人決定 `status: merged`）。
4. **每筆資料可追溯。** 每筆紀錄有 `source_ids`；欄位只來自部分來源時有 `field_sources`。
5. 全部輸出在回傳前以真實 Schema 驗證；不合法 = 程式錯誤，丟出 `BuildError`。

## 2. 輸入

`RawListing(data, source_id)`：`data` 是爬蟲／匯入（D2-01、D2-04）的原始列，鍵固定為：

`exhibitor_name_as_listed`（必填）、`booth`、`hall`、`country`、`website`、`categories`、`products`、`description`、`participation_type`

其他鍵（含 `_row`）忽略。每個用到的 `source_id` 必須提供 `retrieved_at`。國家文字轉 ISO 代碼**只靠呼叫端給的別名表**（不同來源拼法不同，屬來源的對應設定）；沒有內建猜測。

## 3. 標準化規則（`etl/normalize.py`）

| 函式 | 做什麼 | 不做什麼 |
|---|---|---|
| `clean_text` | NFKC、移除控制與零寬字元、空白合併、去頭尾空白 | 不改大小寫、不翻譯、不修拼字 |
| `name_keys` | `exact`：NFKC、casefold、只留字母數字（保留法律型態）。`loose`：再去掉前後的法律型態（Ltd、Inc、GmbH、有限公司、株式会社…） | `loose` **只用於候選**，不用於合併 |
| `normalize_website` | 補 `https://`、主機名稱小寫／去尾端點／punycode、去 fragment 與預設埠 | 拒絕非 http(s)、帶帳密、IP 位址、格式不合的主機名稱 |
| `split_list` | 以 `; | 、；` 與換行分隔、去重、保序、每項最長 500 字 | |
| `normalize_country` | 以給定別名表查詢，結果必須是兩個大寫字母 | 沒有別名就是 `None` |

## 4. 登錄表（`etl/registry.py`）

單一 JSON 檔（慣例 `data/registry/companies.json`），內容為每個公司的 `exact_keys`、`loose_key`、已見網站、國家，以及 `(屆次, company_id) → participation_id`。

- 只增不改：既有國家不會被覆蓋；ID 不會重新指派。
- 原子寫入（暫存檔＋rename），載入時嚴格驗證（格式、重複 ID、未知欄位），壞檔拒絕載入。
- 比對結果：`matched`（唯一且國家不矛盾）、`new`、`country_conflict`（同名但國家不同 → 新公司並回報）、`ambiguous`（多個符合 → 新公司並回報）。
- 同一個（屆次, 公司）永遠得到同一個 `participation_id`（契約：跨資料包穩定）。

**呼叫端責任：** `build_records` 會更新記憶體中的登錄表；成功後由呼叫端 `registry.save()`。失敗就不要存。

## 5. 建構結果（`build_records`）

- 同一屆內，名稱鍵相同的多列**合併成一家公司、一筆參展紀錄**：第一列的名稱為 `name`，其他拼法成為 `aliases`（帶各自來源）；展位／展廳不一致時保留第一個，其餘寫入 `notes`（不默默選擇）。
- `first_seen_at` / `last_seen_at` 取自來源的取得時間；`listing_status` 一律 `listed`（下架判斷屬 D2-08 的跨期比對）；`verification_status` 一律 `unverified`。
- `BuildReport`：`rows_rejected`（無名稱的列，附原因）、`warnings`、`merged_rows`、`candidates`、`conflicts`。

## 6. 不包含

- 跨期／跨展覽的變更比對與下架判斷（D2-08）、官方筆數與完整度報告（D2-09）、規則篩選（D2-10）、組裝資料包（D2-11）。
- 人工合併流程（把候選確認為同一家、寫 `status: merged`）：目前只產生候選清單。
- 內建國家名稱表、分類正規化（屬 AI 側 P1-AI-06）、機率式或模糊比對（刻意不做）。
