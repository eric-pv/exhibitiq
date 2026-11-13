# 展覽來源評估報告：`dsa`（`2026`）

> 依 `source-assessment-template.md`。評估日 2026-11-10，評估者：data（Albert 的 Claude Code）。只記錄實際查到的內容；未查證的列在 §10。
> 這是由人挑選並提供的檔案，不是指定的測試展覽；它被撤下或失效不會阻礙通用系統。結構與 IACP 2026（列印的名單頁）不同，作為 D2-03「第二個不同結構」的真實資料。

## 1. 基本資訊

| 項目 | 內容（來源） |
|---|---|
| exhibition_id／edition_id | `dsa`／`dsa-2026` |
| 名稱 | 19th Defence Services Asia Exhibition & Conference（封面），與 NATSEC ASIA 2026 合辦；名單標題「DEFENCE SERVICE ASIA (DSA) 2026 & NATIONAL SECURITY ASIA (NATSEC ASIA) 2026 PARTICIPATING COMPANIES」 |
| 日期、地點 | 20 – 23 April 2026、MITEC, Kuala Lumpur（封面）→ `2026-04-20`～`2026-04-23`、MITEC、Kuala Lumpur、MY |
| 主辦網站 | www.dsaexhibition.com（封面） |
| 檔案 | 主辦單位的 PDF 名單（49 頁，封面＋48 頁表格，「Updated as of 6 April 2026 (7pm)」，PDF ModDate 2026-04-08T10:03:29Z），sha256 `aa74bf36b1f43a80339fdec608b3ec4e33a558b71a763981d591373ddd2241aa` |

## 2. 結論（資料集索引 `acquisition`）

- `method: file_import`、`status: feasible`：主辦單位以 PDF 表格公布名單，可用通用的 `pdf-layout-table` 適配器完整讀取。
- 1184 列 → 1172 筆參展紀錄（12 列與他列名稱相同且國家相同而合併），`completeness_status: unknown`（名單沒有寫總數；1184 是列號，不是主辦方宣稱的展商數）。

## 3–4. 來源與評估

| 欄位（表頭） | 對應的原始欄位 | 備註 |
|---|---|---|
| No. | `_row` | 1–1184 連續 |
| Exhibitor | `exhibitor_name_as_listed` | 長名稱換行；三行的名稱垂直置中，第一行在列號**上方** |
| Country/Region | `country` | 54 種寫法，以 `data/sources/dsa/dsa-2026.countries.json` 對應 ISO 代碼（UK→GB、UAE→AE、Türkiye→TR 等） |
| aca（攤位） | `booth` | 705 列有值 |
| Pavillion | `hall` | 445 列有值；是國家館或主題館（如「Team Defence Australia (Australia)」「Firearms & Tactical Gear」），不是實體展館編號 |

文字層沒有欄位分隔，因此以文字在頁面上的座標讀取（適配器說明見 `import-file.md` §3）。檢查：
- 1184 列的名稱、國家、攤位、館區，與 pypdf 一般文字擷取逐列一致（空白差異已逐一修正：行尾連字號、強制斷字、全形逗號、字型沒有字寬表時的估算）。
- 人工對照 PDF 畫面抽查第 1、24、49、150、152、154、165、173、186、192、199、851、866、874 列（含三行置中、強制斷字、名稱內的「 - 」與「-」），全部一致。

## 5. 使用條款與限制

- 這是主辦單位為公開發布而製作的名單；檔案由 Albert 提供。**確切下載網址未記錄**，來源紀錄引用封面上的主辦網站 `https://www.dsaexhibition.com/`。
- 本環境的網路只開放 `iacp2026.mapyourshow.com`，因此**沒有**查閱 dsaexhibition.com 的 robots.txt 與使用條款（§10）。
- 名單只有公司名稱、國家、攤位、館區，沒有個人資料。

## 6. 完整度

沒有宣稱的總數 → `unknown`。列號連續、沒有缺號或重複。同名不同國的 6 組沒有合併（例如 L3Harris Technologies 在 TH 與 US 各有一列），另有 20 組只差公司型態或國家的「可能相同」列為候選、未合併（`etl.build_records` 的保守規則）。

## 7. 取得方式與理由

`pdf-layout-table` 適配器（`crawler/pdf_layout_table.py`，通用，不含網站名稱）＋ `data/sources/dsa/dsa-2026.toml`（欄位順序、頁首頁尾文字）＋ `dsa-2026.countries.json` ＋ `dsa-2026.info.json`；以 `python -m etl.import_file ... --country-aliases` 匯入。

## 8. 失敗與限制

- 名單停在 2026-04-06，展覽已於 2026-04-23 結束；之後是否有更新版本未知。
- 名稱經 NFKC 正規化存入（原文在快照）。
- 館區放在 `hall` 欄位（Schema 沒有「館區／國家館」欄位）。

## 9. 建議的來源設定

不適用（不是 `automatic`）。

## 10. 未解事項

- 確切下載網址；dsaexhibition.com 的 robots.txt 與使用條款（需要開放該網站或由 Albert 確認）。
- 公開 repo 是否保留此真實名單：專案負責人決定（CLAUDE.md：開發期間可暫時提交）。

## 11. 來源清單

| source_id | 內容 | 保存 |
|---|---|---|
| `src_01M727Z9TXFH56F0RY7Z3PH14A` | 主辦單位 PDF 名單（4124374 bytes） | Git：`data/raw/dsa/dsa-2026/run_01M727Z9TV8A01MY3X2QWRZJ9Q/snapshots/` |
