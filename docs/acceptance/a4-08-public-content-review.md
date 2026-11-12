# 公開內容與資料安全檢查（A4-08）

> 檢查日期：2026-11-10｜負責人：專案負責人（`ai`）｜repo 自 2026-11-05 起公開（Eric 決定）；開發期間真實資料與公司內部資料可提交，專案結束時改為不公開（Eric 2026-11-09）。**密碼、Token、金鑰一律不提交。**

## 檢查結果

| 範圍 | 檢查內容 | 結果 |
|---|---|---|
| `dev/ai-intelligence` 所有檔案 | GitHub／Anthropic／AWS／Google／Slack 金鑰、私鑰 | 沒有（只有安全檢查自己的測試範例） |
| `dev/data-platform` 所有檔案 | 同上；電子郵件 | 沒有金鑰；只有測試用的假地址 `a@b.com` |
| `gh-pages`（公開網站） | 同上；`npm run pages:check` | 沒有；發布前檢查通過 |
| 網站程式與打包結果 | `npm run security`（金鑰、GitHub／LLM API 呼叫） | 通過；網站不呼叫任何 API、不含憑證 |
| GitHub Actions | workflow 權限 | `dev/data-platform` 目前沒有 workflow；之後新增時須最小權限並設定 concurrency（由資料端負責） |

## 已知的公開內容（依 Eric 決定，開發期間保留）
- IACP 2026 參展商名單（`dev/data-platform`，#113）與其分析結果（#116）。
- 公司內部競品名單（`knowledge/benchmarks/known-competitors.csv`，#109）。
- 專案結束改為不公開時，以上與 Git 歷史一併不公開；公開網站（`gh-pages`）目前只發布合成資料。

## 自動化
- `tests/contract/test_public_content.py`：每次測試掃描所有追蹤中的檔案，出現金鑰樣式就失敗。
- 網站：`npm run security`（打包結果）、`npm run pages:check`（公開網站只發布核准的資料）。
