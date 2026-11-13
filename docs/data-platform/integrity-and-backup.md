# 資料快照、備份與重新生成的驗證

> 工作項目：D4-03｜負責人：data｜程式：`etl/integrity.py`｜測試：`tests/data/test_integrity.py`
> 依賴：D2-06（`crawler/store.py` 快照保存）、D1-04（`etl/package.py`）、D1-05（驗證程式）。本文件只記錄已實作並測試過的行為。

## 1. 三個問題，各用證據回答

| 問題 | 函式／指令 | 判定 |
|---|---|---|
| 原始快照還在、沒被改過？ | `verify_snapshots` ／ `snapshots` | 資料包每個 `snapshot.storage == "git"` 的來源：`snapshot.locator`（從 repo 根目錄起算）的檔案存在，且 sha256 等於 `content_sha256`。`not_stored`（刻意未保存，見 D2-06）與其他儲存方式**只列出，不算已驗證**。不安全的 locator（絕對路徑、`..`）列為問題，不讀檔。 |
| 資料包能從自己的紀錄逐位元組重新產生？ | `check_regenerable` ／ `regen` | 以 `write_package` 把資料包的紀錄重寫到暫存目錄，逐檔比對 8 個檔案與 `content_hash`。manifest 格式不同（契約 §5 允許、驗證程式會接受）也會被指出：那不是程式會寫出的檔案。 |
| 備份還原後完全相同？ | `create_backup`、`verify_backup`、`restore_backup` ／ `backup`、`verify-backup`、`restore` | 見 §2。 |

另以端到端測試驗證「**從原始證據重新建構**」：匯入 → 保存快照 → 建構紀錄 → 組裝資料包後刪除原始輸入檔，只用保存的快照與企業登錄表（`etl.registry`）重新解析、建構與組裝，得到相同的 companies／participations 與相同的 `content_hash`。

## 2. 備份檔

- 一個 `.tar.gz`，第一個成員是 `backup-manifest.json`：`version: 1`、`created_at`、每個資料包（`dataset_id`、路徑、`content_hash`、`data_origin`、已驗證快照數、未保存的 `source_id`）、每個檔案（路徑、sha256、bytes）。
- 內容：資料包 8 個檔案＋它們引用、存在 Git 的原始快照。路徑一律是 repo 相對路徑，還原後結構與 repo 相同。
- **可重現**：成員依路徑排序、`mtime`／uid／gid＝0、無擁有者名稱、mode 0644、gzip 標頭時間＝0。相同輸入與 `created_at` 產生逐位元組相同的檔案。
- **建立前檢查**：資料包必須通過驗證（R1–R11），引用的 Git 快照必須存在且雜湊正確，否則拒絕並不寫檔；已存在的輸出檔不覆寫。
- **驗證**（不解壓）：每個列出的檔案存在、sha256 與大小相符；沒有未列出的成員、重複成員、非一般檔案（連結、目錄）或不安全路徑。
- **還原**：先完整驗證，任何問題都不寫入任何檔案；目標必須是不存在或空的目錄（不覆寫）。寫入後**重新驗證每個資料包**（R1–R11）、比對 `content_hash` 與備份清單、重新檢查快照。即使有人改了資料檔又同步改了清單，還原後的驗證仍會失敗（R8）。

備份檔放在哪裡（Release、外部儲存等）**不在本工作項目決定**；這裡只產生與檢查檔案。Actions Artifact 不是永久保存（CLAUDE.md）。

## 3. 指令

```bash
python -m etl.integrity snapshots [--repo-root .] PACKAGE_DIR...
python -m etl.integrity regen PACKAGE_DIR...
python -m etl.integrity backup --out BUNDLE.tar.gz [--repo-root .] [--created-at 2026-11-09T00:00:00Z] PACKAGE_DIR...
python -m etl.integrity verify-backup BUNDLE.tar.gz
python -m etl.integrity restore BUNDLE.tar.gz TARGET_DIR
```

結束碼：0 全部驗證通過；1 發現問題（JSON 列出）；2 輸入錯誤或拒絕執行（stderr 說明，未寫入任何東西）。

## 4. 驗證（2026-11-09，雲端容器，Python 3.11／3.12／3.13）

- 3 個合成樣本資料包：快照全部驗證、逐位元組重新產生、備份（27 個檔案）→ 驗證 → 還原後每個檔案與原檔相同。
- `tests/data/test_integrity.py` 29 個測試：遺失／被改的快照、不安全 locator、manifest 格式不同、資料檔被改、備份可重現與無時間戳、各項拒絕（覆寫、未通過驗證、快照遺失、不在 repo 內）、被改／遺失／多出的成員、不安全路徑（`../`、絕對路徑、`./`、`//`）、連結、清單版本、還原不覆寫、清單與資料包不符、被偽造清單的還原、從原始證據重新建構。
- 突變測試 26 個（關閉雜湊／存在／路徑安全檢查、把 not_stored 當成已驗證、關閉各項重生比對、關閉建立／驗證／還原的各項拒絕、成員時間戳改為目前時間、未排序、還原時不重新驗證、CLI 結束碼）全部被測試抓到。

## 5. 不包含

- 備份的保存位置、排程與保留期限（需專案負責人決定儲存方式）。
- `not_stored` 或外部儲存快照的內容驗證（沒有檔案可比對；只保留 sha256）。
- 資料包以外的檔案（`data/index/`、`data/history/`）：它們由資料包重新產生（D2-12、D2-08），不需要備份。
- 加密：備份內容與 repo 相同，不應放到公開位置（CLAUDE.md：不得公開私有情報）。
