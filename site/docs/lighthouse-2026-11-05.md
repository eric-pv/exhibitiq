# Lighthouse 實測紀錄（W4-04）

- 日期：2026-11-05；Lighthouse 12.2.1；Chromium（雲端工作區，headless）；對象：`npm run build` 後 `vite preview` 的系統總覽頁（合成資料）。
- 執行方式：`lighthouse http://localhost:4173/ [--preset=desktop] --only-categories=performance,accessibility,best-practices`

| 版本 | 裝置 | 效能 | 無障礙 | 最佳做法 | FCP | LCP | TBT | CLS |
|---|---|---|---|---|---|---|---|---|
| 修正前 | 桌機 | 80 | 96 | 96 | 0.9 s | 1.0 s | 110 ms | 0.342 |
| 修正前 | 手機（模擬 4G、CPU 4x 降速） | 55 | 95 | 96 | 4.8 s | 5.1 s | 550 ms | 0 |
| 修正後 | 桌機 | 82 | 96 | 100 | 0.8 s | 1.0 s | 50 ms | 0.319 |
| 修正後 | 手機（模擬 4G、CPU 4x 降速） | 59 | 95 | 100 | 4.4 s | 5.6 s | 380 ms | 0 |

## 本次修正
- ECharts 改為顯示圖表時才載入（主程式從約 2.1 MB 降為 1.4 MB，另一個 1.0 MB 分出去）。
- 加上 favicon，消除主控台 404 錯誤（最佳做法 96 → 100）。
- 次要文字顏色改用設計 token `textMuted`（提高對比）；統計卡片的無障礙名稱包含畫面上的數字。

## 尚未解決（記錄，不影響功能）
- **手機效能 59：** 主程式仍有 1.4 MB（Ant Design 與資料檔）。下一步是各頁改為按需載入（React.lazy），需要同時調整頁面測試的等待方式，安排在 W3-06／W4-01 一併處理。
- **桌機 CLS 0.32：** 首次載入時側欄與內容排版位移，待 W3-06 調整。
- **對比度：** 仍有部分 Ant Design 標籤（Tag）顏色對比不足。
- 公開部署環境（GitHub Pages 或其他）的數字會不同；發布方式決定後再測一次。
