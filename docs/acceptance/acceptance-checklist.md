# ExhibitIQ 驗收清單與測試案例（A4-01）

> 依據：[`docs/specs/mvp-scope.md`](../specs/mvp-scope.md) §4（V1–V14，Eric 已核定）與 [`DEVELOPMENT_PLAN.md`](../DEVELOPMENT_PLAN.md) §6、V2.5 動態分析設定驗收（D1–D7）。
> 狀態以 `dev/ai-intelligence` 2026-11-05 為準；「✅」表示已有自動測試強制，「◐」表示部分完成，「⏳」表示依賴尚未完成的工作。**最終驗收由專案負責人在階段整合時判定，本表不代表驗收通過。**

## 執行方式（雲端工作區）

```bash
python -m pytest -q tests/contract                     # 契約、Skill、證據、設定檔、可重現性
python skills/exhibitiq/scripts/repro_check.py --check  # A3-08：兩個工作區輸出一致
cd site && npm ci && npm test                          # 資料存取層、頁面、雜湊與 Python 一致
npm run build && npm run build:single && npm run security
npx playwright test                                    # 端到端、三種尺寸截圖（需 vite preview）
```

## MVP 驗收指標

| # | 指標 | 狀態 | 證據（測試或指令） | 尚缺 |
|---|---|---|---|---|
| V1 | 兩組不同結構的展覽資料走同一流程，第二組不改核心程式 | ◐ | `site/src/compare.test.tsx`（範例＋黃金樣本，兩種結構）、`tests/contract/test_golden_v1.py` | 一組真實合法資料（D2-02／D2-03）；A4-10 測試 |
| V2 | 在 Dashboard 新增未收錄的展覽並走完流程 | ◐ | `site/src/add-exhibition.test.tsx`（登錄內容通過 A1-10 Schema、建議 ID、可能重複、不送出任何請求）、`e2e/flow.spec.ts`「W3-07」 | D2-13 workflow；之後的取得、分析與展示 |
| V3 | 取得失敗在系統狀態頁顯示原因，不阻礙其他展覽 | ✅ | `site/src/status.test.tsx`、`e2e/smoke.spec.ts`「status (W2-05)」 | 真實失敗紀錄（資料集索引） |
| V4 | 任一事實欄位可追溯到 `source_id`、取得時間、快照雜湊 | ✅ | `site/src/company-detail.test.tsx`（含「引用不存在的來源 → bundle 失敗」） | — |
| V5 | AI 推論不冒充事實；推論有依據、信心、不確定性 | ✅ | `tests/contract/test_evidence_check.py`（EV1–EV3）、`site/src/opportunities.test.tsx` | — |
| V6 | 評分可拆解；沒有依據的因子 0 分 | ✅ | `test_evidence_check.py`（EV4）、`opportunities.test.tsx`、`test_relate.py`（評分權重） | 評分模型待核定 |
| V7 | 產品建議只引用已核准產品卡 | ✅ | `tests/contract/test_knowledge_v1.py`（AR10、A2-05 draft 卡） | 產品卡核定（A2-05） |
| V8 | 沒有官方筆數時顯示「未知」；不完整時顯示完整度 | ✅ | `site/src/overview.test.tsx`、`exhibitions.test.tsx`、`test_compare.py`（不完整不算比例） | — |
| V9 | 網頁報告與 PDF 內容一致 | ✅ | `site/src/reports.test.tsx`（網頁與 Markdown 章節、結論、來源一致）、`e2e`「reports (W3-04)」（列印版面、PDF） | 自動 PDF workflow（D3-01） |
| V10 | 完整流程：展覽 → 企業 → 商機 → 產品建議 → 報告 → PDF | ◐ | `site/e2e/flow.spec.ts`（W4-01：單一測試走完整條流程，含 PDF）；展示腳本 `docs/acceptance/demo-script.md` | 「新增展覽」一段（W3-07／D2-13）；真實資料 |
| V11 | 桌機、平板、手機都可以操作 | ✅ | `e2e/layout.spec.ts`（9 頁 × 3 尺寸，不得橫向捲動） | 完整響應式調整（W3-06） |
| V12 | 前端沒有 Token、API Key；公開版只含核准內容 | ✅ | `npm run security`、`npm run pages:check`、`site/src/security.test.ts`、`tests/contract/test_public_content.py`（整個 repo）；檢查紀錄 `docs/acceptance/a4-08-public-content-review.md` | — |
| V13 | 資料更新後可重新產生；兩人可在雲端獨立執行 Skill | ◐ | `tests/contract/test_repro.py`、另一個乾淨 clone 驗證一致 | Albert 工作區執行（A4-04）；A4-05 |
| V14 | 合成資料在畫面與報告上明確標示 | ✅ | `DataOriginBanner` 各頁測試、報告「資料狀態」章節（`test_skill_tools.py`） | — |

## 動態分析設定驗收（V2.5）

| # | 指標 | 狀態 | 證據 |
|---|---|---|---|
| D1 | 同一展覽可套用不同主題與模式並保留不同結果 | ✅ | `test_analysis_profile_v1.py`、`save-analysis`（新 `analysis_id` 不覆蓋，`test_save_analysis.py`） |
| D2 | 使用者可以自行新增、刪除關鍵字 | ✅ | `site/src/settings.test.tsx`、`e2e`「settings (W2-06)」 |
| D3 | 修改關鍵字不需要修改核心程式 | ✅ | `test_relate.py::test_keywords_change_without_code_change` |
| D4 | 不使用 BXR 產品資料也能做產業研究 | ✅ | `test_relate.py::test_mode_b_runs_without_any_bxr_cards` |
| D5 | 同一企業可同時符合多種關係 | ✅ | `test_relate.py::test_multi_label_and_never_fact` |
| D6 | 報告可追溯關鍵字、模式、來源與版本 | ✅ | 報告「分析設定」與「版本與追溯附錄」（`test_skill_tools.py`、`reports.test.tsx`） |
| D7 | 關鍵字命中不當成事實 | ✅ | `test_relate.py`（`sufficiency: signal_only`、EV1） |

## 通用性（§6）

| 階段 | 狀態 | 證據 | 尚缺 |
|---|---|---|---|
| Phase 1：兩組不同結構的合成資料 | ✅ | `examples/package` 與 `golden/v1/package` 同一 bundle、同一組頁面（`compare.test.tsx`） | — |
| Phase 2：真實公開來源、第二組資料不改核心程式 | ⏳ | — | D2-02、D2-03 |
| Phase 3：Dashboard 新增未收錄展覽走完流程 | ⏳ | — | W3-07、D2-13 |
| Phase 4：兩組以上端到端、核心程式沒有寫死展覽（測試強制） | ◐ | `tests/contract/test_governance_docs.py`（文件不寫死展覽） | 程式碼掃描與端到端（A4-10） |

## 已知限制
- 所有畫面與分析目前使用合成資料；真實資料由資料工程的擷取與匯入完成後接入。
- 效能實測見 [`site/docs/lighthouse-2026-11-05.md`](../../site/docs/lighthouse-2026-11-05.md)。
