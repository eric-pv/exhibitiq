# ExhibitIQ 開發進度

> 最後更新：2026-11-09（W3-06 跨頁連結與資料關聯）｜負責人：專案負責人（`ai`）
> 工作項目編號見 [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)。
> **更新方式：** 本檔只由 `ai` 修改（V2.2 共用規範修訂由 data 經專案負責人特別授權一併更新本檔，屬一次性例外）（同步到 `dev/data-platform` 時會覆蓋，對方修改會遺失）。資料工程的進度以 Albert 合併到 `dev/data-platform` 的 PR 為準，由 `ai` 讀取後更新本檔；只記錄已經在 GitHub 上查證的狀態。

## 目前階段

**Phase 1**（目標 D1–D4，11/03–11/06），進行中。

## 已完成

| 編號 | 項目 | PR | 合併到 | 合併日期 |
|---|---|---|---|---|
| A1-02、A1-03 | Repo 治理基礎：文件歸位、PR／Issue 模板、分支規則（舊編號 P1-AI-01） | [#2](https://github.com/magician-eric/exhibitiq/pull/2) | `dev/ai-intelligence` | 2026-11-03 |
| A1-04 | 模組邊界與 Schema 版本政策（舊編號 P1-AI-03） | [#4](https://github.com/magician-eric/exhibitiq/pull/4) | `dev/ai-intelligence` | 2026-11-03 |
| — | 第一次共用規範同步 | [#5](https://github.com/magician-eric/exhibitiq/pull/5) | `dev/data-platform` | 2026-11-03 |
| A1-05 | 核心資料契約 Schema v1（`1.0.0-draft.1`，舊編號 P1-AI-04） | [#8](https://github.com/magician-eric/exhibitiq/pull/8) | `dev/ai-intelligence` | 2026-11-03 |
| D1-01 | 雲端 Python 開發與執行環境設定（舊編號 P1-DATA-01） | [#9](https://github.com/magician-eric/exhibitiq/pull/9) | `dev/data-platform` | 2026-11-03 |
| — | 第二次共用規範同步：`schemas/v1/`、`docs/specs/`（來源 `dev/ai-intelligence` @ `127db55`；已查證兩邊一致） | [#10](https://github.com/magician-eric/exhibitiq/pull/10) | `dev/data-platform` | 2026-11-03 |
| D1-03 | 爬蟲／ETL 可重用目錄與程式骨架（舊編號 P1-DATA-02） | [#12](https://github.com/magician-eric/exhibitiq/pull/12) | `dev/data-platform` | 2026-11-03 |
| A1-08 | 簡化開發管理流程：開發計畫、進度檔、Web Dashboard 納入 MVP | [#13](https://github.com/magician-eric/exhibitiq/pull/13) | `dev/ai-intelligence` | 2026-11-03 |
| — | 第三次共用規範同步：V2.1 流程文件（已查證兩邊一致） | [#14](https://github.com/magician-eric/exhibitiq/pull/14) | `dev/data-platform` | 2026-11-03 |
| A1-06 | 分析結果與證據契約（`1.0.0-draft.2`）＋合併人標記規則（Issue #15） | [#16](https://github.com/magician-eric/exhibitiq/pull/16) | `dev/ai-intelligence` | 2026-11-03 |
| — | 第四次共用規範同步：A1-06、合併人規則（已查證兩邊一致） | [#17](https://github.com/magician-eric/exhibitiq/pull/17) | `dev/data-platform` | 2026-11-03 |
| D1-07 | 來源設定、執行日誌與錯誤格式 | [#18](https://github.com/magician-eric/exhibitiq/pull/18) | `dev/data-platform` | 2026-11-03 |
| D1-10 | （歷史紀錄）MSPO 來源評估，結論為網頁上看不到參展商名單；**不是任何後續工作的依賴** | [#19](https://github.com/magician-eric/exhibitiq/pull/19)、[#20](https://github.com/magician-eric/exhibitiq/pull/20) | `dev/data-platform` | 2026-11-03 |
| — | V2.2 共用規範修訂同步到 `dev/ai-intelligence`（通用展覽平台、8 個主選單、通用性驗收） | [#22](https://github.com/magician-eric/exhibitiq/pull/22) | `dev/ai-intelligence` | 2026-11-03 |
| A1-07 | 資料集索引與管線狀態契約（`1.0.0-draft.3`） | [#23](https://github.com/magician-eric/exhibitiq/pull/23) | `dev/ai-intelligence` | 2026-11-03 |
| — | V2.3 共用規範修訂：移除特定展覽依賴 | [#24](https://github.com/magician-eric/exhibitiq/pull/24) | `dev/ai-intelligence` | 2026-11-03 |
| — | V2.2 共用規範修訂（`dev/data-platform` 版本） | [#21](https://github.com/magician-eric/exhibitiq/pull/21) | `dev/data-platform` | 2026-11-04 |
| — | 第五次共用規範同步：A1-07（Schema `1.0.0-draft.3`）與 V2.3（已查證兩邊一致） | [#26](https://github.com/magician-eric/exhibitiq/pull/26) | `dev/data-platform` | 2026-11-04 |
| D1-04 | 資料包讀寫工具（JSONL、雜湊、manifest 完整性、來源索引） | [#27](https://github.com/magician-eric/exhibitiq/pull/27) | `dev/data-platform` | 2026-11-04 |
| W1-01 | 前端骨架（React、Vite、TS、Ant Design、ECharts、Vitest、Playwright、單一 HTML 打包）＋根目錄 `.gitignore` | [#28](https://github.com/magician-eric/exhibitiq/pull/28) | `dev/ai-intelligence` | 2026-11-04 |
| W1-02 | 設計系統、共用 Layout、8 個主選單、狀態元件；自動模式規則（Issue #29） | [#30](https://github.com/magician-eric/exhibitiq/pull/30) | `dev/ai-intelligence` | 2026-11-04 |
| W1-03 | 資料存取層、bundle 產生程式、系統總覽（合成資料）；**Phase 1 Dashboard 可視化成果完成** | [#32](https://github.com/magician-eric/exhibitiq/pull/32) | `dev/ai-intelligence` | 2026-11-04 |
| — | 第六次共用規範同步：自動模式規則與進度 | [#33](https://github.com/magician-eric/exhibitiq/pull/33) | `dev/data-platform` | 2026-11-04 |
| A1-09 | BXR 產品知識庫結構與分析分類架構（`1.0.0-draft.4`；只有結構） | [#34](https://github.com/magician-eric/exhibitiq/pull/34) | `dev/ai-intelligence` | 2026-11-04 |
| — | 第七次共用規範同步：A1-09（`1.0.0-draft.4`） | [#35](https://github.com/magician-eric/exhibitiq/pull/35) | `dev/data-platform` | 2026-11-04 |
| A1-01 | 競賽 MVP 範圍與驗收指標（**Eric 已核定**） | [#36](https://github.com/magician-eric/exhibitiq/pull/36) | `dev/ai-intelligence` | 2026-11-04 |
| A1-10 | 展覽登錄契約（`1.0.0-draft.5`）；**ai 的 Phase 1 工作全部完成** | [#39](https://github.com/magician-eric/exhibitiq/pull/39) | `dev/ai-intelligence` | 2026-11-04 |
| — | V2.4 流程：獨立作業（階段為檢查點、測試通過後自行合併、data 端自行同步） | [#44](https://github.com/magician-eric/exhibitiq/pull/44) | `dev/ai-intelligence` | 2026-11-04 |
| A2-01 | Skill 入口、輸入輸出與報告驗收規格 | [#47](https://github.com/magician-eric/exhibitiq/pull/47) | `dev/ai-intelligence` | 2026-11-04 |
| A2-02 | 黃金樣本（第二組不同結構的合成資料與預期結果） | [#49](https://github.com/magician-eric/exhibitiq/pull/49) | `dev/ai-intelligence` | 2026-11-04 |
| A2-03 | Skill 輔助程式與安裝使用說明 | [#51](https://github.com/magician-eric/exhibitiq/pull/51) | `dev/ai-intelligence` | 2026-11-04 |
| A2-04 | 資料包批次讀取與版本驗證 | [#52](https://github.com/magician-eric/exhibitiq/pull/52) | `dev/ai-intelligence` | 2026-11-04 |
| A2-06 | 分類詞草稿（待核定）、分類規則、`classify` | [#54](https://github.com/magician-eric/exhibitiq/pull/54) | `dev/ai-intelligence` | 2026-11-04 |
| A2-07 | 商機評分模型 opportunity@1（草稿待核定）與 `score` | [#55](https://github.com/magician-eric/exhibitiq/pull/55) | `dev/ai-intelligence` | 2026-11-04 |
| W2-02 | 企業清單：搜尋（含別名）、篩選（網址同步）、排序、分頁、CSV 匯出；共用 DataTable | [#56](https://github.com/magician-eric/exhibitiq/pull/56) | `dev/ai-intelligence` | 2026-11-04 |
| W2-03 | 企業詳情：欄位來源（`SourceRef`）、別名、參展紀錄、最後更新時間 | [#58](https://github.com/magician-eric/exhibitiq/pull/58) | `dev/ai-intelligence` | 2026-11-04 |
| W2-04 | 商機分析頁：排名、評分拆解（`ScoreBreakdown`）、關係分類、建議、來源引用 | [#59](https://github.com/magician-eric/exhibitiq/pull/59) | `dev/ai-intelligence` | 2026-11-04 |
| A2-11 | 證據驗證 `evidence_check.py`（EV1–EV7；驗證失敗不能發布） | [#60](https://github.com/magician-eric/exhibitiq/pull/60) | `dev/ai-intelligence` | 2026-11-04 |
| W2-01 | 展覽搜尋與展覽詳情（資料集索引；取得方式、評估、各屆次取得／驗證／完整度） | [#62](https://github.com/magician-eric/exhibitiq/pull/62) | `dev/ai-intelligence` | 2026-11-04 |
| A2-14 | 分析結果版本化回存 `save-analysis` | [#63](https://github.com/magician-eric/exhibitiq/pull/63) | `dev/ai-intelligence` | 2026-11-04 |
| A2-12、A2-13 | 報告版型與 Markdown 報告 | [#65](https://github.com/magician-eric/exhibitiq/pull/65) | `dev/ai-intelligence` | 2026-11-04 |
| W3-04 | AI 報告中心、`ReportViewer`、PDF 匯出 | [#66](https://github.com/magician-eric/exhibitiq/pull/66) | `dev/ai-intelligence` | 2026-11-04 |
| A2-08 | 企業關係初篩 `relate`（V2.5 將由 A2-16 改為多標籤） | [#67](https://github.com/magician-eric/exhibitiq/pull/67) | `dev/ai-intelligence` | 2026-11-04 |
| A2-15 | 分析設定檔契約（Schema `1.0.0-draft.6`，舊資料相容）；開發計畫 V2.5 | [#69](https://github.com/magician-eric/exhibitiq/pull/69) | `dev/ai-intelligence` | 2026-11-04 |
| A2-05 | 8 張 BXR 產品卡（draft，無規格）與 A 模式主題 `bxr-opportunity` | [#70](https://github.com/magician-eric/exhibitiq/pull/70) | `dev/ai-intelligence` | 2026-11-04 |
| A2-16 | 分析工具改讀設定檔、多標籤關係、`opportunity@2` 草稿 | [#71](https://github.com/magician-eric/exhibitiq/pull/71) | `dev/ai-intelligence` | 2026-11-04 |
| W2-06 | 「分析設定」主選單（第 9 項） | [#72](https://github.com/magician-eric/exhibitiq/pull/72) | `dev/ai-intelligence` | 2026-11-04 |
| A2-17 | Skill 三種分析模式；報告「分析設定」章節 | [#73](https://github.com/magician-eric/exhibitiq/pull/73) | `dev/ai-intelligence` | 2026-11-04 |
| A2-09 | 趨勢與跨展覽比較 `compare` | [#74](https://github.com/magician-eric/exhibitiq/pull/74) | `dev/ai-intelligence` | 2026-11-04 |
| W3-01 | 展覽情報與比較頁 | [#75](https://github.com/magician-eric/exhibitiq/pull/75) | `dev/ai-intelligence` | 2026-11-05 |
| W2-05 | 資料及系統狀態頁 | [#76](https://github.com/magician-eric/exhibitiq/pull/76) | `dev/ai-intelligence` | 2026-11-05 |
| W4-03 | 錯誤處理（統一錯誤與空狀態） | [#77](https://github.com/magician-eric/exhibitiq/pull/77) | `dev/ai-intelligence` | 2026-11-05 |
| A3-05 | 報告版本與追溯附錄 | [#78](https://github.com/magician-eric/exhibitiq/pull/78) | `dev/ai-intelligence` | 2026-11-05 |
| W4-02 | 所有頁面三種尺寸的截圖與版面測試 | [#79](https://github.com/magician-eric/exhibitiq/pull/79) | `dev/ai-intelligence` | 2026-11-05 |
| W4-05 | 安全檢查 `npm run security` | [#80](https://github.com/magician-eric/exhibitiq/pull/80) | `dev/ai-intelligence` | 2026-11-05 |
| A3-08 | Skill 可重現性檢查 | [#81](https://github.com/magician-eric/exhibitiq/pull/81) | `dev/ai-intelligence` | 2026-11-05 |
| W3-05 | CSV 匯出（Excel 可開、防公式注入） | [#82](https://github.com/magician-eric/exhibitiq/pull/82) | `dev/ai-intelligence` | 2026-11-05 |
| W4-04 | Lighthouse 實測紀錄與初步優化 | [#83](https://github.com/magician-eric/exhibitiq/pull/83) | `dev/ai-intelligence` | 2026-11-05 |
| A4-01 | 驗收清單與測試案例 | [#84](https://github.com/magician-eric/exhibitiq/pull/84) | `dev/ai-intelligence` | 2026-11-05 |
| A3-01 | 報告視覺規格 | [#85](https://github.com/magician-eric/exhibitiq/pull/85) | `dev/ai-intelligence` | 2026-11-05 |
| W4-06 | 公開展示網址、帳號改名 `eric-pv`、多檔案發布 | [#87](https://github.com/eric-pv/exhibitiq/pull/87)、[#88](https://github.com/eric-pv/exhibitiq/pull/88) | `dev/ai-intelligence` | 2026-11-05 |
| — | Eric 核定：產品卡、`opportunity@2`、預設詞庫 | [#89](https://github.com/eric-pv/exhibitiq/pull/89) | `dev/ai-intelligence` | 2026-11-05 |
| A3-05（成本） | 分析成本欄位（Schema `1.0.0-draft.7`）與勾選顯示 | [#91](https://github.com/eric-pv/exhibitiq/pull/91) | `dev/ai-intelligence` | 2026-11-05 |
| A2-10 | 展覽商務價值與拜訪候選（不含預算）、EV8 | [#92](https://github.com/eric-pv/exhibitiq/pull/92) | `dev/ai-intelligence` | 2026-11-05 |
| W4-06（檢查） | 公開網頁發布檢查 `pages:check` | [#86](https://github.com/magician-eric/exhibitiq/pull/86) | `dev/ai-intelligence` | 2026-11-05 |
| W3-03 | BXR 產品推薦頁（只顯示已核定產品卡、引用該產品的 AI 建議） | [#93](https://github.com/eric-pv/exhibitiq/pull/93) | `dev/ai-intelligence` | 2026-11-05 |
| A3-04、W3-02 | 歷史趨勢：`trend` 指令與「展覽情報與比較」頁歷史趨勢區塊（只有一個年度時顯示「資料不足」） | [#94](https://github.com/eric-pv/exhibitiq/pull/94) | `dev/ai-intelligence` | 2026-11-05 |
| A3-07（工具） | 已知企業關係名單規格與 `validate-known`／`benchmark`；名單等 Albert 提交（Issue #90） | [#95](https://github.com/eric-pv/exhibitiq/pull/95) | `dev/ai-intelligence` | 2026-11-05 |
| A3-06、W4-01 | 競賽展示腳本與主要操作流程端到端測試 | [#96](https://github.com/eric-pv/exhibitiq/pull/96) | `dev/ai-intelligence` | 2026-11-05 |
| A3-02 | 報告「數據摘要」章節與國家／地區圖表（`report-templates@4`） | [#97](https://github.com/eric-pv/exhibitiq/pull/97) | `dev/ai-intelligence` | 2026-11-05 |

`A1-02` 的兩條 dev 分支已建立（`dev/ai-intelligence`、`dev/data-platform`）。

## 進行中

| 編號 | 項目 | 狀態 |
|---|---|---|
| W3-06 | 跨頁連結與資料關聯（圖表點選篩選、企業 ↔ 分析 ↔ 報告 ↔ 展覽 ↔ 比較）、詳情頁三種尺寸版面測試 | 本 PR |

## 待處理（Phase 1）

| 負責 | 編號 |
|---|---|
| ai | （無；A1-10 合併後 ai 的 Phase 1 工作全部完成） |
| data | D1-02、D1-05、D1-06、D1-08、D1-09、D1-11 |
| data | 資料包 manifest 等檔案的 `schema_version` 使用 `1.0.0-draft.5`（A1-10 同步後）；D2-12 依 A1-07 產生資料集索引；D2-13 依 A1-10 寫入 `data/registry/` |

## 阻礙事項

個別展覽或來源無法取得資料**不列為阻礙**：記錄在資料集索引與來源評估報告後，改用其他公開來源（總規範 §1.1）。

| 項目 | 影響 | 狀態 |
|---|---|---|

## Eric 決定紀錄（2026-11-05）

| 事項 | 決定 |
|---|---|
| BXR 產品卡 | 8 張依目前內容（名稱與功能定位）核定；之後會新增產品與型錄 |
| 商機評分 | `opportunity@2` 核定；配分可在「分析設定」修改 |
| 預設詞庫 | 28 個分類詞核定為起點 |
| A2-10 | 只建議展覽的商務價值，不評估預算金額（預算屬於其他系統） |
| 分析成本 | 比賽中顯示、正式版不顯示：做成可勾選 |
| 比賽展示流程（A3-06） | 新增展覽 → 企業 → 商機 → 匯出報告；A 模式 |
| 人工標準樣本（A3-07） | 已知競爭同行名單由 Albert 提供 |
| 真實資料 | 開發期間暫時放進公開 repo；正式版改為不公開 |
| 展示網址 | 帳號改名為 `eric-pv`；https://eric-pv.github.io/exhibitiq/（公司防火牆阻擋中，待 IT 放行） |

## 待專案負責人決定

| 事項 | 需要在何時決定 |
|---|---|
| 是否需要網頁一鍵執行（新增展覽、觸發擷取、執行分析）：需要後端代理或 GitHub App 等新服務；預設不做，改用 Actions 手動執行（總規範 §4.1） | Phase 3 開始前 |
| 是否在 Actions 自動執行 AI 分析（需要 API 金鑰與費用） | Phase 3 開始前 |

## 已存在的 Issue（歷史紀錄）

Issue #15（合併人標記規則，跨人協調）是新制下的 Issue，規則已由 #17 同步到 `dev/data-platform`，已關閉。

Issue #1、#3、#6、#7、#11 是取消強制 Issue 之前建立的，保留為歷史紀錄。#1、#3、#7 已關閉；#6、#11 屬於資料工程（對應的 PR #9、#12 已合併），由 Albert 自行處理。
