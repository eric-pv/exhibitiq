# 競賽展示案例與操作腳本（A3-06）

> 負責人：專案負責人（`ai`）｜依據：Eric 2026-11-05 決定（展示流程：新增展覽 → 企業 → 商機 → 匯出報告；A 模式 BXR 商機分析）
> 本腳本的瀏覽器操作由 `site/e2e/flow.spec.ts`（W4-01）逐步自動驗證；畫面或流程改變時，腳本與測試一起修改。
> **狀態（2026-11-09）：** 網站目前只有合成資料（全站顯示「合成資料」橫幅）。步驟 2 的「新增展覽」表單已完成（W3-07），連到的 GitHub Actions workflow 要等 D2-13；真實資料要等 D2-02、D2-03。下表「現況」欄寫的是今天實際看得到的內容。

## 1. 展示前準備（前一天）

| 項目 | 怎麼做 |
|---|---|
| 網址 | https://eric-pv.github.io/exhibitiq/ 。公司網路被防火牆阻擋時，改用手機網路，或使用下面的備案 |
| 備案（不需要網路） | 在雲端工作區執行 `cd site && npm ci && npm run build:single`，下載 `dist-single/index.html`，直接用瀏覽器開啟 |
| 報告 PDF | 先在「AI 報告中心」匯出一份 PDF 備用；比賽時勾選「顯示分析成本」 |
| 確認測試 | `cd site && npm run build && npx playwright test e2e/flow.spec.ts`，必須通過 |
| 資料 | 確認「資料及系統狀態」頁的資料版本與預期一致；真實資料放進公開 repo 前要經 Eric 同意 |

## 2. 操作腳本（約 8 分鐘）

| # | 頁面（主選單） | 操作 | 要說的重點 | 現況 |
|---|---|---|---|---|
| 1 | 系統總覽 | 打開首頁 | ExhibitIQ 是**通用**展會情報平台，不綁定任何展覽；數字都來自資料包，旁邊標示完整度 | ✅ |
| 2 | 展覽搜尋與新增 | 按「新增展覽」，填寫展覽名稱、國家、年份、官網 → 產生並下載登錄內容（符合 A1-10 格式）→（D2-13 完成後）連到 GitHub Actions；再搜尋既有展覽、打開展覽詳情 | 新增展覽不需要改程式；網站不送出資料、不需要帳號；取得方式有自動、半自動、匯入、人工四種，取得失敗也會記錄原因 | ◐ 表單完成（W3-07）；Actions workflow 待 D2-13 |
| 3 | 展覽情報與比較 | 選兩個以上展覽並排比較；往下看「歷史趨勢」 | 同一組指標比較不同展覽；只有一個年度時誠實顯示「資料不足」，不推測趨勢 | ✅ |
| 4 | 參展商與企業情報 | 搜尋企業 → 打開企業詳情 → 點欄位旁的來源 | **每個欄位都能追溯來源**：網址、取得時間、內容雜湊 | ✅ |
| 5 | 商機分析與評分 | 看排名 → 展開評分拆解 → 點企業 | AI 推論有明確標示；評分拆解到每個因子和來源，**沒有依據的因子不計分** | ✅ |
| 6 | 分析設定 | 切換主題、新增一個關鍵字 | 主題和關鍵字由使用者決定，不寫死；本機修改不會改變已產生的分析結果 | ✅ |
| 7 | BXR 產品推薦 | 看產品卡與引用的建議 | 只顯示已核定的產品卡；建議連到報告 | ✅ |
| 8 | AI 報告中心 | 打開報告 → 勾選分析成本 → 匯出 PDF | 網頁和 PDF 是同一份分析結果；附錄記錄版本、來源與分析設定，可以追溯 | ✅ |
| 9 | 資料及系統狀態 | 看取得、驗證與通知 | 系統會顯示資料哪裡不完整、哪個來源失敗 | ✅ |

## 3. AI 分析怎麼產生（口頭說明或預錄）

分析由雲端 Claude Code 的 ExhibitIQ Skill 執行，網站本身不執行 AI、不含任何金鑰：

```bash
python skills/exhibitiq/scripts/exhibitiq_tools.py select <exhibition_id>
python skills/exhibitiq/scripts/exhibitiq_tools.py relate <package_dir> --profile bxr-opportunity
python skills/exhibitiq/scripts/exhibitiq_tools.py score  <package_dir> --profile bxr-opportunity
python skills/exhibitiq/scripts/exhibitiq_tools.py value  <package_dir> --profile bxr-opportunity
python skills/exhibitiq/scripts/exhibitiq_tools.py validate-analysis <analysis.json> <package_dir>
python skills/exhibitiq/scripts/exhibitiq_tools.py save-analysis     <analysis.json> <package_dir>
```

驗證（`validate-analysis`，證據規則 EV1–EV8）不通過的分析結果不能發布。

## 4. 回答問題時不能說的話

- 不宣稱資料完整：完整度不是「完整」時，就照畫面上的完整度說明。
- 不把關鍵字命中或 AI 推論說成已確認的事實或商業關係。
- 不提供預算或金額建議（Eric 2026-11-05：預算屬於其他系統）。
- 合成資料只用來展示功能，不能說成真實展覽的結果。
- 「歷史趨勢」只在有兩個以上年度的資料包時才有；目前顯示「資料不足」是正確結果。

## 5. 正式比賽前還要完成

| 項目 | 負責 | 影響 |
|---|---|---|
| 至少一組真實、合法取得的展覽資料（D2-02），以及第二個不同結構的展覽（D2-03） | data | 步驟 1、3、4 改用真實資料；通用性驗收 V1 |
| 「新增展覽」workflow（D2-13）；表單（W3-07）已完成，workflow 合併後把檔名填入 `site/src/data/registration.ts` 的 `ADD_EXHIBITION_WORKFLOW` | data → ai | 步驟 2 的新增展覽示範 |
| 真實資料的 AI 分析結果與報告 | ai | 步驟 5、7、8 |
| 已知競爭同行名單（A3-07，Issue #90） | data | 用 `benchmark` 比對 AI 的競爭對手判斷，作為準確度說明 |
