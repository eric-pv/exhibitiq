# 報告視覺規格（A3-01）

報告沿用 Dashboard 的設計系統（W1-02），**不另設樣式**。網頁、PDF、Markdown 都由同一份分析結果與同一份版型（`templates/report-templates.json`）產生。

## 1. 來源

| 項目 | 唯一來源 |
|---|---|
| 顏色、間距、字級、圓角 | `site/src/theme/tokens.ts`（`color`、`space`、`fontSize`、`radius`） |
| 章節與順序 | `skills/exhibitiq/templates/report-templates.json` |
| 網頁／PDF 呈現 | `site/src/components/ReportViewer.tsx` |
| PDF 版面 | `site/src/theme/print.css`（A4、邊界 14 mm） |
| Markdown | `exhibitiq_tools.py report` |

## 2. 版面

- **A4 直式**，邊界 14 mm；只印報告本身（選單、按鈕、彈出視窗都隱藏）。
- 標題層級：報告標題 H3（`fontSize.h3`）、章節 H4；章節間距 `space.lg`。
- 章節標題不與內容分頁（`break-after: avoid`）；每個評分區塊、清單項目、表格列不跨頁斷開。
- 長 ID 與雜湊值自動換行，不得撐開版面（手機與 PDF 皆同）。
- 表格：評分拆解使用共用 `ScoreBreakdown`；欄位依序為因子、得分、理由、依據。

## 3. 標示規則（顏色一定搭配圖示與文字，不能只靠顏色）

| 內容 | 呈現 |
|---|---|
| 來源事實 | `ClaimBadge`：已查證／待查證／人工確認（`color.success`／`color.neutral`） |
| AI 推論（結論、評分、關係、建議） | `ClaimBadge`「AI 推論」（`color.inference`，紫色，刻意與「已查證」區隔） |
| 資料不足、未知 | `ClaimBadge`「資料不足」／「未知」（`color.warning`）；評分因子寫「資料不足，不計分」 |
| 合成資料 | 「資料狀態」章節第一行粗體說明；網頁另有頁首橫幅 |
| 完整度不是「完整」 | 數字旁 `CompletenessIndicator`，並加警告「資料不完整，結論與排名可能遺漏」 |
| 產品資料未核定 | 「資料狀態」章節警告（A 模式使用 draft 產品卡時） |
| 來源引用 | 編號 `[n]`，同一份報告內同一來源同一編號；來源附錄列出 ID、類型、網址、取得時間、快照雜湊 |

## 4. 章節（所有報告類型）

基本資訊 → 分析設定 → 資料狀態 → 摘要 → 結論 → （評分與排名、關係分類：有資料時一定出現）→ 建議 → 不確定性與限制 → 來源附錄 → 版本與追溯附錄。沒有內容的章節仍保留標題並寫「無」。

## 5. 驗收

- 網頁與 Markdown 章節、結論、來源一致：`site/src/reports.test.tsx`。
- 列印版面隱藏選單、產生 PDF：`site/e2e/smoke.spec.ts`「reports (W3-04)」。
- 手機不出現橫向捲動：`site/e2e/layout.spec.ts`。
- 顏色只定義在 `tokens.ts`：`site/src/app.test.tsx`「colours are defined only in theme/tokens.ts」。
