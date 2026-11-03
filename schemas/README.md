# schemas/ — ExhibitIQ 唯一資料契約

- **負責人：** 專案負責人（`ai`）
- **格式：** JSON Schema Draft 2020-12
- **版本政策：** [`VERSIONING.md`](VERSIONING.md)
- **變更紀錄：** [`CHANGELOG.md`](CHANGELOG.md)
- **目錄負責人與同步程序：** [`docs/architecture/module-boundaries.md`](../docs/architecture/module-boundaries.md)

## 目前狀態

尚未有任何 Schema 檔。第一版核心資料契約由 **P1-AI-04** 建立在 `schemas/v1/`，版本號 `1.0.0-draft.1`。

## 預定結構

```text
schemas/
├── README.md         # 本文件
├── VERSIONING.md     # 版本、相容性與變更程序
├── CHANGELOG.md      # 每次版本變更的紀錄
└── v1/               # P1-AI-04 建立
    ├── VERSION       # 整組 Schema 的完整版本號
    └── <entity>.schema.json
```

## 使用方式

- 驗證程式（由資料工程負責，位於 `etl/`）從本機 `schemas/v<MAJOR>/` 載入 Schema，不得透過網路取得，也不得在其他位置複製欄位定義。
- 需要新增或修改欄位時，依 [`VERSIONING.md`](VERSIONING.md) 第 5 節開 Issue 提出。
