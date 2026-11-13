# 組裝資料包（AI 分析用，含 manifest 與來源索引）

> 工作項目：D2-11｜負責人：data｜程式：`etl/assemble.py`
> 本文件只記錄已實作並測試過的行為；尚未做的部分列在「不包含」。

## 1. 位置

整條資料鏈：

```
匯入／擷取 (D2-01、D2-04) → 保存證據 (D2-06) → 清洗與去重 (D2-07) → 組裝資料包 (D2-11) → 驗證程式 R1–R11 (D1-05)
```

`assemble_package()` 把前面步驟的產物寫成 `docs/specs/data-package-contract.md` 規定的資料包：`<root>/<exhibition_id>/<year>/<dataset_id>/`，8 個檔案。**只有通過驗證程式才會發布。**

## 2. 流程與保證

1. 由屆次 ID 與建立時間（轉成 UTC，必須有時區）產生 `dataset_id`（`<edition_id>.<YYYYMMDDTHHMMSSZ>`）。目標目錄已存在即拒絕（資料包不可變；要新版就用更晚的 `created_at` 並以 `previous_dataset_id` 串連）。
2. 先寫入隱藏的暫存目錄（`.assembling-<dataset_id>`），再跑 `etl.validate.validate_package`。
3. 有任何 finding：刪除暫存目錄、丟出 `AssembleError`（附 findings），**不會留下半成品，也不會發布**。
4. 通過才 `rename` 到正式位置；rename 前再檢查一次目標是否已被別人建立（不覆蓋）。
5. 同樣輸入產生相同的 `content_hash`（可重現）。

## 3. 完整度（算出來的，不是宣稱的）

| 條件 | `completeness_status` |
|---|---|
| 沒有提供官方筆數 | `unknown`（官方筆數與來源記為 `null`） |
| 官方筆數（附來源）＝ 狀態為 `listed` 的參展紀錄數 | `complete` |
| 官方筆數與已收集數不同（不論多或少） | `partial` |

官方筆數必須附 `source_id` 且該來源在本包的 `sources.jsonl` 內，否則拒絕；筆數必須是非負整數。**不接受估計值。** `removed` 的參展紀錄不計入已收集數。

## 4. 使用

```python
sources, crawl_run = load_run(run_dir)            # run_dir 來自 crawler.store（D2-06）
built = build_records(listings, edition_id=..., retrieved_at=..., registry=registry, country_aliases=...)
package = assemble_package(
    "data/packages", exhibition=..., edition=..., companies=built.companies, participations=built.participations,
    sources=sources, crawl_runs=[crawl_run], data_origin="collected", producer={"name": "exhibitiq-etl", "version": "0.1.0"},
    created_at=datetime.now(timezone.utc), official_count=OfficialCount(120, official_source_id),
)
registry.save("data/registry/companies.json")     # 只有在 assemble 成功後才存登錄表
```

`exhibition.json`、`edition.json` 的內容（展覽名稱、日期、場地等）來自展覽登錄資料與來源評估，本模組不產生也不猜測。

## 5. 測試

整條鏈（CSV 匯入 → 存證 → 建構紀錄 → 組裝 → 驗證程式）在測試中端對端執行。資料全是合成的，`data_origin` 為 `synthetic`。

## 6. 不包含

- 變更紀錄（`changes.jsonl`）的產生與下架判斷（D2-08；目前由呼叫端傳入，第一個資料包必須為空）。
- 官方筆數的取得與完整度報告（D2-09）、發布與資料集索引（D2-12）、把資料包提交到 Git 的流程。
- 展覽／屆次紀錄的內容產生。
