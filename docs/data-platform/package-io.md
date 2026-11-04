# 資料包讀寫工具

> 工作項目：D1-04｜負責人：data｜程式：`etl/jsonl.py`、`etl/hashing.py`、`etl/package.py`
> 依據：`docs/specs/data-package-contract.md` §3、§5、§6（Schema `1.0.0-draft.3`）。本文件只記錄已實作並測試過的行為。

## 1. 範圍

**做的事：** 把資料依契約寫成位元組可重現的資料包、計算 manifest 的完整性欄位、嚴格讀回。

**不做的事：**

- **不驗證 Schema。** 唯一的資料包驗證程式（R1–R11）是 D1-05，載入 `schemas/v1/`。本模組只處理序列化與雜湊，不知道任何欄位定義（只知道每種 JSONL 檔的主鍵名稱）。
- 不指派 ID（`company_id` 等）、不決定 `completeness_status`、不做企業去重（屬 D2-07、D2-09）。
- 不綁定任何特定展覽；測試只使用契約的合成範例。

## 2. 模組

| 模組 | 內容 |
|---|---|
| `etl/jsonl.py` | `canonical_line`、`serialize_records`（依主鍵位元組順序排序、主鍵唯一）、`serialize_single`、`parse_jsonl_bytes`／`read_jsonl`／`read_single`（嚴格讀取）、`loads_strict` |
| `etl/hashing.py` | `sha256_of_bytes`、`content_hash`（契約 §6 的演算法） |
| `etl/package.py` | `write_package`、`read_package`、`compute_integrity`、`read_manifest`／`write_manifest`、`package_path`、`SourceIndex` |

## 3. 使用方式

```python
from etl.package import write_package, read_package, package_path

out = package_path("data/packages", "example-expo", 2026, "example-expo-2026.20261103T000000Z")
manifest = write_package(
    out,
    exhibition=exhibition_record,          # 1 筆
    edition=edition_record,                # 1 筆
    records={"companies": [...], "participations": [...], "sources": [...],
             "crawl_runs": [...], "changes": []},   # 省略的集合會寫成 0 位元組空檔
    manifest={...},  # 除了 files、record_counts、content_hash 以外的所有欄位
)
pkg = read_package(out, require_canonical=True)
```

`write_package` 的行為：

- **位元組可重現：** 同樣的輸入（不論紀錄順序）產生同樣的位元組與 `content_hash`。
- **不可變：** 目標目錄已存在就拒絕（`PackageError`），不覆蓋。
- **不留殘骸：** 先寫入同一個父目錄下的暫存目錄，全部完成後才改名；任何失敗都會清掉暫存目錄。
- **完整性欄位由程式計算：** `files`（`sha256`、`bytes`、`records`）、`record_counts`、`content_hash` 從實際寫出的位元組算出；呼叫端若自己提供會被拒絕。
- **`source_snapshot_ids`、`crawl_run_ids`：** 省略時由紀錄衍生（依位元組順序排序）；提供時必須與紀錄一致，否則拒絕（避免之後驗證 R10 才發現）。
- `manifest.json`：縮排 2、鍵排序、UTF-8、LF、結尾換行（契約只建議 `indent=2`，格式不限）。

## 4. 嚴格讀取

`read_jsonl` 拒絕：UTF-8 BOM、CR、非 UTF-8、空白行、缺少結尾換行、不是物件的行、**重複的物件鍵**、NaN／Infinity。錯誤訊息含檔名與行號。`require_canonical=True` 時還要求每一行與 canonical 形式逐位元組相同（對應契約 R5 的一部分）。

## 5. 驗證結果（2026-11-03，雲端容器）

核心驗證：**用本工具重新產生契約的範例資料包 `schemas/v1/examples/package/`，7 個資料檔逐位元組相同，`manifest.json` 內容相同，`content_hash` 為 `sha256:68fc94dcaeaed1d23842f327b6b3cd05e07cca6610372ebb086622b03fb4d74b`**，與契約 §6 的 shell 參考指令（`sha256sum … | LC_ALL=C sort -k2 | sha256sum`）的輸出一致。

| Python | 結果 |
|---|---|
| 3.11 | 128 passed |
| 3.12 | 128 passed |
| 3.13 | 128 passed |

反向驗證：故意改壞 12 處（不排序鍵、跳脫非 ASCII、不依主鍵排序、`content_hash` 分隔符、不依檔名排序、`.json` 檔的 `records`、不可變性檢查、失敗不清暫存、ID 不排序、`package_path` 允許 `..`、不檢查 manifest 與紀錄一致、核心程式出現特定展覽名稱），測試全部失敗。第一輪曾發現「失敗後清除暫存目錄」沒有被測到，已補上測試。

## 6. 已知限制

- 檔名與主鍵名稱（`company_id`、`participation_id`、`source_id`、`crawl_run_id`、`change_id`）寫在 `etl/package.py`，來源是契約 §3、§5 的文字，不是 Schema 欄位定義。契約改變時要同步修改，並由「與範例資料包逐位元組比對」的測試把關。
- 暫存目錄改名不是跨程序的鎖；同時寫入同一個目標由 workflow 的 concurrency 控制（D1-02、D1-08）負責。
- 只有序列化層級的檢查。內容是否符合 Schema、參照是否完整，都是 D1-05。
- 沒有串流寫入：整個資料包在記憶體中組裝。對目前預期的規模（數千筆）沒有問題；規模大到有問題時再改。
- `tests/data/test_no_hardcoded_exhibition.py` 只做粗略的名稱比對，不能證明核心程式沒有硬編特定展覽，只能抓到明顯的退化。
