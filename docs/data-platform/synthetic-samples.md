# 合成測試資料（兩組不同結構的展覽）

> 工作項目：D1-06｜負責人：data｜位置：`data/samples/`｜產生程式：`data/samples/build_samples.py`
> **這些資料全部是虛構的，不代表任何真實展覽或企業，不得當作事實使用。** 每個資料包的 `manifest.data_origin` 是 `synthetic`，國家為 `ZZ`，網址只使用保留的範例網域（`example.com`／`.org`／`.net`）。
> 與 Eric 的範例資料包 `schemas/v1/examples/package/`（屬 `ai`，用於契約測試）是兩回事；這裡是資料工程自己的測試資料。

## 1. 內容

| | `sample-fair`（欄位豐富） | `demo-trade-show`（欄位精簡） |
|---|---|---|
| 資料包 | 同一屆兩版：v1 → v2（`previous_dataset_id` 串接） | 單一資料包（2025） |
| 原始快照格式 | HTML 表格（`raw/exhibitors-v1.html`、`-v2.html`） | CSV（`raw/exhibitors.csv`） |
| 來源種類 | 官方名單（保存於 Git）、官網（未保存快照並說明原因） | CSV 匯入、人工輸入、官方文件 |
| 欄位 | 展位、展廳、產品、別名、網域、`field_sources`、中文名稱 | 只有必填欄位 |
| 查證狀態 | `unverified`、`verified`、`insufficient_data` | `unverified`、`human_confirmed`、`insufficient_data` |
| 參展類型 | `exhibitor`、`co_exhibitor` | `exhibitor`、`sponsor`、`unknown` |
| 完整度 | v1 `partial`（頁面寫 5 家、列出 4 家）→ v2 `complete`（頁面寫 4 家、列出 4 家） | `complete`（3 家） |
| 變更紀錄 | v2 有 5 筆：展位新增、參展紀錄下架、企業合併、企業與參展紀錄新增 | 無（第一個資料包） |
| 其他 | 已下架的參展紀錄保留（`listing_status: "removed"`）；已合併企業（`merged_into`） | **一次失敗的擷取被記錄**（`access_blocked`，403，依規定停止、不繞過），改用 CSV 匯入，資料包仍然完整 |

路徑：`data/samples/<exhibition_id>/<edition_year>/<dataset_id>/`（資料包，依契約 §3），`data/samples/<exhibition_id>/raw/`（原始快照）。

## 2. 為什麼這樣設計

- **通用性驗收（V2.3）**：用兩組結構不同的資料證明驗證器、讀寫工具與（之後的）分析程式不依賴特定展覽。展覽之間的差異只在資料裡，不在程式裡。
- **原始快照是真的**：`source.content_sha256` 是 `raw/` 檔案實際的 sha256，`snapshot.locator` 指向該檔；D2-04 的匯入轉換工具可以直接拿這些檔案當測試輸入。
- **來源原文與正規化名稱分開**：`exhibitor_name_as_listed` 與來源頁面逐字相同（例如 `SYNTHETIC OPTICS LTD`），公司的 `name` 則是正規化後的 `Synthetic Optics Ltd.`。
- **失敗只記錄，不阻礙**：呼應 V2.3「特定來源取得失敗，不得阻礙通用系統繼續開發」。

## 3. 重新產生

```bash
python data/samples/build_samples.py --force   # 刪除兩個樣本目錄後重建（不加 --force 時，已存在就拒絕）
python -m etl.validate data/samples/sample-fair/2026/sample-fair-2026.20261104T010000Z   # 驗證每個資料包
```

- 程式是決定性的：固定 ID、固定時間，相同輸入產生逐位元組相同的結果。
- `schema_version` 讀自 `schemas/v1/VERSION`。**Schema 草案版本升級並同步到 `dev/data-platform` 後，必須重新產生**；否則驗證器的 R3 與「樣本與產生程式輸出一致」的測試會失敗，這是刻意的提醒。manifest 不參與 `content_hash`，所以升版只改變 manifest，資料檔案與 `content_hash` 不變。
- 不要手改樣本檔案：改產生程式，再重新產生。

## 4. 驗證結果（2026-11-04，雲端容器）

- 3 個資料包都通過 `python -m etl.validate`（R1–R11，Schema `1.0.0-draft.3`）。
- `tests/data/test_samples.py` 共 21 個測試，證明驗證器**證明不了**的事：
  - 原始快照存在，且雜湊等於來源宣告的 `content_sha256`。
  - 原始名單頁寫的總數、列數、名稱與資料包完全一致。
  - 兩組真的在結構上不同（欄位集合、來源種類、原始格式、完整度、變更與失敗紀錄的有無、查證狀態）。
  - 全部標示為合成：`data_origin`、國家 `ZZ`、只用保留網域、沒有真實展覽名稱。
  - 已提交的檔案與產生程式的輸出逐位元組相同，且產生程式是決定性的、不覆蓋已存在的資料包。
- **突變測試：** 故意改壞產生程式與樣本檔案 13 處（雜湊寫錯、改成真實國家／展覽名稱／網域、改成 `collected`、v2 沒串到 v1、名單總數或列數對不上、HTML 名稱與來源原文不一致、移除整組欄位、手改原始快照與已提交的紀錄），全部被測試抓到。
- **實作中抓到的真實錯誤：** 第一版樣本的 HTML 寫 `Synthetic Optics Ltd.`，參展紀錄的 `exhibitor_name_as_listed` 卻是 `SYNTHETIC OPTICS LTD`；契約要求後者保留來源原文。驗證器看不出這種錯，是「名單內容與資料包一致」的測試抓到的，已修正。

## 5. 限制

- 資料量很小（3–5 家企業），目的是展示結構差異，不是壓力測試。
- 不含展覽登錄資料：登錄內容與存放位置屬 A1-10，尚待專案負責人決定。
- 兩組的欄位差異都在 Schema 既有的選填欄位範圍內；沒有、也不應該用到 Schema 沒有的欄位。
- 原始快照只有 HTML 與 CSV；PDF 與 Excel 的匯入範例待 D2-04 需要時再加。
- 產生程式為了匯入 `etl`，會把 repo 根目錄加進 `sys.path`；請從 repo 內執行。
