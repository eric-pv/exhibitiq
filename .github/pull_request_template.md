<!--
ExhibitIQ PR 模板（依《ExhibitIQ 專案總規範》§9）
- 功能 PR 的 base 必須是任務擁有者自己的 dev 分支：
  - 專案負責人：dev/ai-intelligence
  - 資料工程：dev/data-platform
- 只有階段整合 PR（integration/phase-N）的 base 才能是 main。
-->

## Issue
- Closes #
- Phase：
- 負責人角色：ai / data

## 分支
- Head：`feature/<ai|data>/<issue>-<slug>`
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
（執行日誌、Actions 連結、範例輸出或截圖）

## 檢查清單
- [ ] 只修改本 Issue 允許的路徑
- [ ] 未提交帳密、Token 或未核准的機密資料
- [ ] 沒有虛構資料、筆數、來源或測試結果
- [ ] Base 分支正確，未指向 `main`（階段整合 PR 除外）
