> **合併人：Eric** ／ > ⚠️ **合併人：Albert。Eric 請勿合併。**（擇一保留；標題開頭同樣加上【Eric 合併】或【Albert 合併】）

<!--
ExhibitIQ PR 模板（依《ExhibitIQ 專案總規範》§9）
- 功能 PR 的 base 必須是任務擁有者自己的 dev 分支：
  - 專案負責人：dev/ai-intelligence
  - 資料工程：dev/data-platform
- 只有階段整合 PR（integration/phase-N）的 base 才能是 main。
-->

## 工作項目
- 編號（`docs/DEVELOPMENT_PLAN.md`）：
- Phase：
- 負責人角色：ai / data
- 相關 Issue（若有；一般工作不需要）：

## 分支
- Head：`feature/<ai|data>/<工作項目編號>-<slug>`
- Base：`dev/ai-intelligence` / `dev/data-platform`

## 變更摘要

## 變更檔案

## 測試命令與結果
```text
（貼上實際執行的命令與輸出；未執行請寫明原因）
```

## Schema 相容性
- [ ] 無 Schema 影響
- [ ] 有 Schema 變更（已取得專案負責人核准，並同步更新範例、驗證器與文件）

## 已知限制

## 成果證據
（執行日誌、Actions 連結、範例輸出）

## 畫面截圖／預覽
（修改 `site/` 時必填：桌機與手機截圖、預覽 artifact 連結，並標示畫面中是真實資料還是合成資料）

## 檢查清單
- [ ] 只修改自己負責的路徑（`docs/architecture/module-boundaries.md` §2）
- [ ] 未提交帳密、Token 或未核准的機密資料
- [ ] 沒有虛構資料、筆數、來源或測試結果
- [ ] 沒有在核心程式寫死特定展覽（總規範 §1.1）
- [ ] Base 分支正確，未指向 `main`（階段整合 PR 除外）
