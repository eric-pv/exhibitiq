# schemas/ — ExhibitIQ 唯一資料契約

- **負責人：** 專案負責人（`ai`）
- **格式：** JSON Schema Draft 2020-12
- **版本政策：** [`VERSIONING.md`](VERSIONING.md)
- **變更紀錄：** [`CHANGELOG.md`](CHANGELOG.md)
- **目錄負責人與同步程序：** [`docs/architecture/module-boundaries.md`](../docs/architecture/module-boundaries.md)

## 目前狀態

- 版本：`1.0.0-draft.3`（Phase 1 草案期）
- 核心資料契約（P1-AI-04）：`common`、`exhibition`、`edition`、`company`、`participation`、`source`、`crawl_run`、`manifest`、`change`
- 人看的規格：[`docs/specs/data-package-contract.md`](../docs/specs/data-package-contract.md)
- AI 分析結果與證據契約（A1-06）：`analysis_result`；規格 [`docs/specs/analysis-result-contract.md`](../docs/specs/analysis-result-contract.md)
- 資料集索引與管線狀態契約（A1-07）：`dataset_index`；規格 [`docs/specs/dataset-index-contract.md`](../docs/specs/dataset-index-contract.md)

## 預定結構

```text
schemas/
├── README.md         # 本文件
├── VERSIONING.md     # 版本、相容性與變更程序
├── CHANGELOG.md      # 每次版本變更的紀錄
└── v1/
    ├── VERSION                # 整組 Schema 的完整版本號
    ├── common.schema.json     # 共用定義（ID、時間、雜湊、列舉）
    ├── <entity>.schema.json   # 各實體
    └── examples/              # 合成範例（測試向量）
        ├── package/           # 完整資料包
        ├── analysis/          # 分析結果範例（以 package/ 為輸入）
        ├── index/             # 資料集索引範例（含取得失敗的展覽）
        └── change.example.json
```

## 使用方式

- 驗證程式（由資料工程負責，位於 `etl/`）從本機 `schemas/v<MAJOR>/` 載入 Schema，不得透過網路取得，也不得在其他位置複製欄位定義。
- 需要新增或修改欄位時，依 [`VERSIONING.md`](VERSIONING.md) 第 5 節開 Issue 提出。
