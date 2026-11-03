# ExhibitIQ 專案總規範 — 競賽版 V2.1

> **最高層規格文件。** 給專案負責人與同事各自的 ChatGPT 完整閱讀，也供 Claude Code 參照。所有指令均須以目前 GitHub Repository 的實際狀態為準。此版取代舊版所有「每項 PR 由負責人審查／合併」及「全部工作結束才建立 PR」的說法。
>
> **V2.1（2026-11-03）：** 取消每個工作項目都要建立 Issue 的規定；四階段的詳細工作清單移到 [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)，進度記錄在 [`PROGRESS.md`](PROGRESS.md)；Web Dashboard 列為競賽 MVP 必要模組，每個階段都要交付可在瀏覽器操作的成果。

## 1. 專案目的與邊界

ExhibitIQ 是全球動力科技（Big x Reality）為內部 AI 應用實戰挑戰賽開發的「AI 多展會情報分析與決策系統」。**真正的 AI 功能發生在使用 Claude Code Skill 分析資料時**，不只是以 AI 協助撰寫程式。

主要成果：自動／手動擷取展覽及企業公開資訊；保存來源與歷史；輸出可供 AI 處理的機器格式資料包；由 Claude Code Skill 讀取並分析潛在客戶、競爭對手、合作對象、技術與市場趨勢；依 BXR 產品知識推薦展品、參展／參觀策略、拜訪對象；產出有來源的展會與市場報告；以 **Web Dashboard** 提供可搜尋、篩選、查看分析、比較資料與匯出報告的操作介面（競賽 MVP 必要模組）。MSPO 為第一個主要驗證展覽，TADTE 為第二個跨展會重用驗證案例。

**優先順序：** 可運作、可驗證、可重複使用、可展示 > 完整商業級介面與基礎設施。沒有證據不得宣稱已取得完整參展名單或完成準確市場預測。

## 2. 唯一確定的工作流程（不可改寫）

- **你（專案負責人）**：負責架構、AI Skill、產品知識、分析及報告；每個自己的工作項目自行透過 ChatGPT 產生 Claude Code 指令、自行執行、自行確認並合併自己的功能 PR 到 `dev/ai-intelligence`。**每個階段兩人的項目全部完成後，由你驗收、向 ChatGPT 索取該階段整合指令，交給 Claude Code 執行整合、測試並決定是否進入下一階段。**
- **同事（資料工程負責人）**：負責爬蟲、匯入、ETL、GitHub 資料儲存與自動化、資料品質與指定展示功能。每個自己的工作項目自行透過她的 ChatGPT 產生 Claude Code 指令、自行執行、自行確認並合併自己的功能 PR 到 `dev/data-platform`。**不負責你的 PR，不負責階段整合與最終驗收。**
- **兩邊的 ChatGPT**：根據本文件、`CLAUDE.md`、[`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) 中的工作項目和最新 Repo 狀態，將**一個工作項目**轉成可直接交給 Claude Code 的完整指令；不擅自變更架構、跨越他人負責範圍或假設不存在的檔案。
- **兩邊的 Claude Code**：在雲端執行開發、測試、提交、建立 PR；依指令把 PR 的 **base 設為自己的長期開發分支**。任務擁有者自己合併 PR。不得把日常功能 PR 指向 `main`。
- **階段整合**：只有當雙方該階段所有工作都完成、PR 已各自合併至各自的開發主線後才啟動。你檢查 PR／測試紀錄，讓 ChatGPT 根據兩條分支現況產生整合指令；Claude Code 在 `integration/phase-N` 整合兩條開發線，處理衝突並執行端到端驗證。你驗收通過後才合併到 `main`，然後以整合後的 `main` 同步下一階段的兩條開發主線。

**特別強調：每個工作項目都有 PR；每個人自行合併自己的 PR；你只做每個階段完成後的整合與驗收。** 不需要你逐項審查同事的 PR。

## 3. GitHub 分支與權限

| 分支 | 用途 | 誰負責合併 |
|---|---|---|
| `main` | 僅保存各階段驗收通過的整合版本 | 你 |
| `dev/ai-intelligence` | 你的持續開發主線 | 你 |
| `dev/data-platform` | 同事的持續開發主線 | 同事 |
| `feature/ai/<工作項目編號>-<slug>` | 你的單項任務分支；PR base=`dev/ai-intelligence` | 你 |
| `feature/data/<工作項目編號>-<slug>` | 同事的單項任務分支；PR base=`dev/data-platform` | 同事 |
| `integration/phase-N` | 階段完成後的整合分支；PR base=`main` | 你 |

每項任務：開發計畫中的工作項目 → ChatGPT 指令 → Claude Code 開發與測試 → PR（可在 GitHub 前端看到）→ 任務擁有者自行合併到自己的 dev 分支 → 下一項工作。一般工作不需要建立 Issue（見 §9）。PR 需列出工作項目編號、變更檔案、測試結果、資料格式影響、已知限制。若測試未通過，先修正再合併；PR 存在不等於工作已完成。

**階段同步：** 完成 `integration/phase-N` → `main` 後，下一階段開始前，兩條 `dev/*` 必須由整合後 `main` 更新；採用安全合併／必要時重建分支，不強制覆寫未備份的工作。若有跨分支共用 Schema 變更，先由你批准並在兩邊以相同契約實作；不必提前做程式整合。

## 4. 技術與成本原則：100% 雲端、GitHub 優先

- **唯一 Private Monorepo**：GitHub 為程式碼、規格、版本化資料及報告的中心。
- **不依賴任何人的本機運算**：兩人的電腦只用瀏覽器／遠端 Claude Code 操作。需執行 Python、測試或工具時，使用具終端機的雲端工作區（例如 GitHub Codespaces，須確認實際帳號支援 Claude Code）或 GitHub Actions。
- **GitHub Actions**：手動或排程執行爬蟲、ETL、Schema 驗證、測試、資料包生成與可公開報告的發布。排程可能延遲，Actions 並非永不停止的常駐服務。
- **GitHub 檔案式資料儲存**：JSON／JSONL／CSV／manifest，保留來源及版本。**GitHub 不是資料庫伺服器**；比賽版不導入 PostgreSQL、Supabase、常駐 FastAPI、VPS，除非你另行批准。
- 大型、頻繁變動的快照不可無限制累積在 Git history；依資料量選擇 Releases、Actions Artifacts 或日後核准的物件儲存。Actions Artifacts 可能有保留期限，不可當作唯一永久資料來源。須記錄資料包位置、雜湊、版本及取得時間。
- GitHub Pages 只能發布經你核准的非機密靜態成果；Private Repo **不代表 GitHub Pages 網站自動保密**。不可將公司敏感資料、個資、金鑰發布到公開網站。各階段的 Dashboard 私有預覽使用 GitHub Actions artifact 或雲端預覽；對外展示網址的方式由你另行核准。
- Skill 以 `skills/exhibitiq/SKILL.md`、references、scripts 組成。可在有 GitHub 存取權的 Claude Code 雲端工作環境使用；**不假設 Claude 網頁聊天會自動安裝或執行此 Skill**。
- GitHub Actions 寫入資料需使用專用受限權限與 concurrency 控制；不要讓爬蟲 workflow 自動寫入 `main` 而繞過階段驗收。比賽期間建議寫入專用資料分支／建立資料更新 PR／或保存版本化資料產物，經規定流程納入整合版本。

## 5. 模組與目錄規範

```text
exhibitiq/
├── .github/workflows/          # crawl、validate、publish
├── crawler/                    # 各展覽來源擷取器
├── etl/                        # 清洗、企業去重、品質檢查
├── schemas/                    # 唯一資料契約與版本
├── data/
│   ├── samples/                # 公開／合成測試資料
│   ├── raw/                    # 來源快照或其索引
│   ├── normalized/             # 標準化 JSONL
│   ├── packages/               # AI 分析資料包或其索引
│   ├── index/                  # 資料集索引與管線狀態
│   └── history/                # 差異與歷史紀錄
├── knowledge/bxr-products/     # 經核准的產品知識
├── skills/exhibitiq/           # Skill、規則、工具
├── reports/                    # 分析結果及報告
├── site/                       # Web Dashboard（靜態 React SPA）
├── tests/                      # 單元／契約／整合測試
├── docs/                       # 規格、開發計畫、進度、操作說明
├── CLAUDE.md
└── README.md
```

禁止兩人各自重新建立一套爬蟲框架、Schema、報告驗證器、來源索引或前端元件。共用功能只保留一份；各模組使用契約互通。**同事的輸出是資料包；你的輸入是資料包。**

## 6. 資料契約與證據

- `schemas/` 是唯一契約來源，含 `schema_version`；修改共用欄位必須先經你核准，更新樣本、驗證器與文件。
- 區分 `exhibition`（展覽）、`edition`（屆次）、`company`（企業）、`participation`（參展紀錄）、`source`（來源）、`crawl_run`（擷取批次）、`analysis_run`（分析批次）。企業 ID 需穩定，名稱／網域／別名不可草率視為同一家公司。
- 資料包建議包含 `manifest.json`、`companies.jsonl`、`participations.jsonl`、`sources.jsonl`、`changes.jsonl`，必要時另附 BXR 產品知識與歷史分析索引。
- `manifest.json` 至少包含：`schema_version`、`dataset_id`、`exhibition_id`、`edition_year`、`created_at`、`source_snapshot_ids`、`record_counts`、`content_hash`、`completeness_status`。
- 分析結果至少包含：`analysis_id`、`input_dataset_id`、`input_hash`、`skill_version`、`generated_at`、`evidence_source_ids`、`conclusions`、`uncertainties`、`recommendations`、`review_status`；可取得時另記 model 版本。
- 爬蟲／ETL 僅執行可重現的資料整理、規則分類與初篩，不把 AI 推論寫成來源事實；初篩不可刪除原始紀錄。區分已驗證、待驗證、AI 推論、人工確認、資料不足。
- 每個市場結論都應附來源與時間；無法確認則標示未知，不得捏造企業、展位、數量、技術能力、報價、趨勢或引文。
- MSPO 2026 曾有約 1,209 筆的目標規模討論，但不代表目前已成功取得完整名單；實際筆數與完整度必須重新查證。

## 7. 分析功能範圍

1. 展會基本資訊、參展商結構與國家／產業分布。
2. 企業情報、別名與跨展會／跨年度身分整合。
3. 潛在客戶與商機排序。
4. 合作夥伴、代理商與通路機會。
5. 競爭對手與產品技術比較。
6. 競品可能展出內容（明確標示為預測）。
7. 技術、應用、能力、問題、需求與產業趨勢。
8. BXR 產品適配、展品組合與差異化建議。
9. 參展／參觀／不參加的決策與預算假設。
10. 必訪企業、洽談議題與已知展位資訊。
11. 跨展會、跨年度比較與定期市場報告。
12. 報告保存、來源追溯、重新分析及人工審核；以上分析都在 Web Dashboard 呈現，AI 推論一律標示，不得顯示為已查證事實。
13. 展後 CRM／成效回饋：比賽版預留結構，不強制完成整套 CRM。

BXR 產品範圍包含 AI XR SUT BOX、BXR POLICE BOX、GP-S、UAV／USV 相關模擬、RWG90、標槍模擬器及兵棋圖台；實際能力以經你確認的產品資料為準。

## 8. 四個階段：交付關卡，不是時間表

四個階段的**詳細工作項目、負責人、依賴與驗收條件**統一記錄在 [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)，本節只定義每個階段的關卡。每個階段都必須交付**可在瀏覽器操作的 Dashboard 版本**，並標示哪些是真實資料、哪些是合成資料；只有文件、終端機輸出或測試通過，不算階段成果。

| 階段 | 目標 | 可視化成果（關卡） |
|---|---|---|
| Phase 1 — 架構與雲端開發基礎 | 契約、模組邊界、雲端環境、驗證工具、Dashboard 架構與設計系統 | 以明確標示的合成資料，在瀏覽器看到 Dashboard 初版並切換主要頁面 |
| Phase 2 — 核心功能平行開發 | MSPO 擷取與資料包、Skill 與分析、Dashboard 呈現真實資料 | 在網頁查看 MSPO 資料、搜尋企業、查看 AI 分析結果與商機推薦；資料不完整時顯示完整度 |
| Phase 3 — 功能完善與競賽展示 | TADTE 跨展會驗證、產品推薦、報告中心、PDF 匯出、完整響應式 | 實際操作從展會選擇、企業分析、產品推薦到報告匯出的完整流程 |
| Phase 4 — 競賽驗收、發布與交接 | 端到端測試、資料來源驗證、安全檢查、最終展示 | 評審可以實際操作的 Dashboard，搭配完整分析案例與可匯出的報告 |

**每個階段的驗收與整合（你）：** 雙方都完成開發計畫中該階段的工作，PR 都已各自合併到自己的 dev 分支後，你取得兩條分支現況與 PR 清單，請 ChatGPT 產生該階段整合指令，由 Claude Code 在 `integration/phase-N` 整合、執行端到端測試（含 Dashboard 與截圖），你驗收通過後才更新 `main`。Phase 4 結束時建立競賽版 Release。

## 9. 工作項目、PR 與 Issue

- **一般工作不需要建立 Issue**，直接依 [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) 的工作項目開發。
- **Issue 只用於：** Bug、重大需求變更、跨人協調、需要追蹤的問題。既有的 Issue 保留為歷史紀錄。
- **每個可以獨立驗收的工作項目都要有 PR**，指向任務擁有者的 dev 分支，包含工作項目編號、變更摘要、測試命令與結果、Schema 相容性、限制、可視化成果（修改 `site/` 時附截圖或預覽）或執行日誌連結。
- 進度記錄在 [`PROGRESS.md`](PROGRESS.md)，由你依已合併的 PR 更新。

**單項 PR 的確認者是該項目擁有者；階段整合與驗收者才是你。** 若有跨人員規格衝突，暫停該工作項目，開 Issue 由你決定；不能各自修改規格後在最後碰運氣。

## 10. 競賽版不做與後續擴充

不強制：PostgreSQL、常駐 API、登入權限平台、完整 CRM、大規模商業級資料庫、全自動雲端 LLM 分析、複雜後台。Web Dashboard 是讀取版本化檔案的靜態 SPA，不屬於常駐 API 或複雜後台。未來需要時再將檔案式儲存替換為資料庫，保持 `schemas/` 與 Skill 的資料讀取介面穩定。

**本文件為唯一開發總規範。發生衝突時，優先順序：你當次明確決策 > 最新核准的專案總規範 > `CLAUDE.md` > `DEVELOPMENT_PLAN.md` > ChatGPT 產生的指令。**
