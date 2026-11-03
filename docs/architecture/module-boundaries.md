# ExhibitIQ 模組邊界與目錄負責人

> 狀態：Phase 1 核定版（P1-AI-03，Issue #3）；V2.1（2026-11-03）修訂：`site/` 改由 `ai` 負責，同步範圍加入 `docs/specs/`、開發計畫與進度檔
> 依據：[`docs/ExhibitIQ_專案總規範.md`](../ExhibitIQ_專案總規範.md) §5、§6，以及專案負責人 2026-11-03 的分工決定。
> 本文件與總規範衝突時，以總規範及專案負責人當次決策為準。

## 1. 角色

| 代號 | 角色 | 長期開發主線 | 功能分支 |
|---|---|---|---|
| `ai` | 專案負責人：架構、Schema 契約、AI Skill、產品知識、分析、報告、Web Dashboard、階段整合 | `dev/ai-intelligence` | `feature/ai/<issue>-<slug>` |
| `data` | 資料工程同事：爬蟲、ETL、資料驗證程式、資料儲存、資料集索引、GitHub Actions（含前端建置與預覽 workflow） | `dev/data-platform` | `feature/data/<issue>-<slug>` |

## 2. 目錄負責人（唯一負責人）

「唯一負責人」是唯一可以在自己的開發主線上建立、修改、刪除該路徑內容的角色。另一方**可以閱讀與引用**，但不得修改；需要變更時依第 3 節提出。

規則：**比對時以最長（最具體）的路徑為準。** 例如 `data/samples/golden/` 歸 `ai`，即使 `data/` 歸 `data`。

| 路徑 | 唯一負責人 | 內容 | 備註 |
|---|---|---|---|
| `CLAUDE.md` | ai | Claude Code 規則 | 共用規範，需同步（第 4 節） |
| `README.md` | ai | 專案入口 | |
| `docs/` | ai | 總規範、開發計畫、進度、工作流程、架構、規格 | 共用規範，需同步（第 4 節）；`docs/PROGRESS.md` 只由 `ai` 更新 |
| `docs/data-platform/` | data | 爬蟲、ETL、Actions 的操作與維護文件 | |
| `.github/ISSUE_TEMPLATE/` | ai | Issue 模板 | 共用規範，需同步 |
| `.github/pull_request_template.md` | ai | PR 模板 | 共用規範，需同步 |
| `.github/workflows/` | data | crawl、validate、publish workflow | 權限與 concurrency 依總規範 §4 |
| `schemas/` | ai | **唯一資料契約**（JSON Schema Draft 2020-12）、版本政策、變更紀錄 | 共用契約，需同步；變更程序見 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) |
| `crawler/` | data | 各展覽來源擷取器 | |
| `etl/` | data | 清洗、去重、品質檢查、**資料驗證程式** | 驗證程式讀取 `schemas/`，不得另行定義契約 |
| `data/` | data | `raw/`、`normalized/`、`packages/`、`history/` 等資料產物 | Raw evidence 不可變更 |
| `data/samples/golden/` | ai | 整合測試用的黃金樣本（預期輸入／輸出） | 合成資料，須明確標示 |
| `data/samples/mspo/` | data | MSPO 格式的公開或合成測試資料 | 合成資料，須明確標示 |
| `knowledge/` | ai | BXR 產品知識庫與分析分類架構 | 只收錄經專案負責人確認的產品資料 |
| `skills/exhibitiq/` | ai | Claude Code Skill、references、scripts | |
| `reports/` | ai | 分析結果與報告 | |
| `site/` | ai | Web Dashboard（靜態 React SPA）：設計系統、共用元件、頁面、資料存取層、bundle 產生程式、前端測試；前端套件設定放在 `site/package.json` | 建置、預覽與發布 workflow 在 `.github/workflows/`，屬於 `data`；**公開發布前必須經專案負責人核准** |
| `tests/contract/` | ai | Schema 契約測試、黃金樣本測試、規範文件檢查 | |
| `tests/data/` | data | 爬蟲、ETL、驗證程式、資料包的測試 | |
| `pyproject.toml` | data | Python 專案與依賴設定 | 雲端 Python 環境屬同事 Phase 1 第 1 項 |
| `requirements.txt` | data | Python 依賴清單（若採用） | `ai` 需要的套件透過 Issue 提出 |
| `.devcontainer/` | data | 雲端工作區設定（若採用） | |

**未列出的路徑：** 新增頂層目錄或新的 `tests/`、`data/samples/` 子目錄之前，先由專案負責人指定負責人並更新本表。

## 3. 跨範圍修改

1. 需要修改對方負責的路徑時，**不要直接改**；開 Issue 說明需求，指定給該路徑的負責人。
2. 由負責人在自己的功能分支實作，PR base 指向自己的 dev 主線，由負責人自行合併。
3. 涉及 `schemas/` 的需求一律依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) 第 5 節的變更程序處理。
4. 衝突或規格不明時暫停該工作項目，由專案負責人決定（總規範 §9）。

## 4. 共用規範與契約的同步

### 4.1 為什麼需要

兩條 dev 主線在階段整合前不會合併；但 `data` 必須依照 `ai` 制定的規範與 Schema 開發。總規範 §3 允許「共用 Schema 變更先由你批准，並在兩邊以相同契約實作；不必提前做程式整合」。因此共用檔案以**單向、只限共用檔案**的方式同步到 `dev/data-platform`。

### 4.2 同步範圍（只有這些路徑）

- `CLAUDE.md`
- `docs/`（**不含** `docs/data-platform/`）
- `.github/ISSUE_TEMPLATE/`、`.github/pull_request_template.md`
- `schemas/`
- 舊版編號規範檔的刪除：`01_ExhibitIQ_專案總規範.md`、`02_CLAUDE.md`、`03_雙方ChatGPT_工作指令模板.md`、`04_階段整合_ChatGPT指令模板.md`、`05_工作流程與驗收檢查表.md`（內容已原封不動移至 `docs/`）

**不同步：** `tests/contract/`、`data/samples/golden/`、`knowledge/`、`skills/`、`reports/`、`site/` 及任何 `ai` 的功能程式。這些等階段整合時才進入對方分支。

### 4.3 程序

1. 專案負責人合併一個改動共用檔案的 PR 到 `dev/ai-intelligence`。
2. 從 `dev/data-platform` 建立 `feature/data/sync-shared-<YYYYMMDD>`。
3. 只取共用路徑（不使用 merge／cherry-pick 整條 commit，避免帶入功能程式）：

   ```bash
   git checkout origin/dev/ai-intelligence -- CLAUDE.md docs/ExhibitIQ_專案總規範.md docs/DEVELOPMENT_PLAN.md docs/PROGRESS.md docs/workflow docs/architecture docs/specs .github/ISSUE_TEMPLATE .github/pull_request_template.md schemas
   ```

   第一次同步另外刪除舊版編號規範檔（4.2 所列）。之後若 `docs/` 新增其他共用子目錄，一併列入上述命令並更新本節。`git checkout` 不會刪除來源端已移除的檔案；這類檔案要另外 `git rm`，4.4 的檢查會列出它們。
4. PR base=`dev/data-platform`，PR 描述附上 4.4 的一致性檢查結果。
5. **由同事自行合併**（她是 `dev/data-platform` 的負責人）。專案負責人不需審查。

### 4.4 一致性檢查

兩條主線上的共用檔案必須逐位元組相同。以下命令輸出為空即表示一致：

```bash
git fetch origin dev/ai-intelligence dev/data-platform
git diff --stat origin/dev/ai-intelligence origin/dev/data-platform -- CLAUDE.md docs/ExhibitIQ_專案總規範.md docs/DEVELOPMENT_PLAN.md docs/PROGRESS.md docs/workflow docs/architecture docs/specs .github/ISSUE_TEMPLATE .github/pull_request_template.md schemas
```

### 4.5 限制

- 同步不是階段整合：不合併任何功能程式，不更動 `main`。
- `main` 在 Phase 1 整合前仍保留舊版檔名；GitHub 只會在 `main` 上自動套用 Issue／PR 模板。

## 5. 資料工程獨立開發指引

`data` 不需要等待 `ai` 即可進行的 Phase 1 工作：雲端 Python 環境、PR 驗證 workflow、爬蟲／ETL 目錄骨架、資料輸出不直接覆蓋 `main` 的 workflow、來源設定與錯誤格式的程式結構。

依賴 Schema（P1-AI-04）的工作：JSONL／manifest／來源索引讀寫工具、資料驗證程式、MSPO 合成測試資料。在 Schema 進入 `dev/data-platform` 之前：

- 可以先寫讀寫與驗證的**程式框架**，以「從 `schemas/v<MAJOR>/` 載入 Schema 檔」的方式設計，不要把欄位寫死在程式裡。
- 不得在 `etl/`、`crawler/` 或 `tests/data/` 另外定義一份平行的 Schema 或欄位清單。暫時性的測試資料只能放在 `tests/data/`，且不得被當作契約。
- 驗證程式是**唯一一份**；`skills/exhibitiq/` 日後需要驗證時直接呼叫它，不另寫一套。
- 對 Schema 有需求或疑問時開 Issue，依 [`schemas/VERSIONING.md`](../../schemas/VERSIONING.md) 第 5 節處理。

## 6. 技術約定

- Schema：JSON Schema Draft 2020-12。
- 測試：Python、`jsonschema`、`pytest`。
- 依賴套件由 `data` 的雲端 Python 環境設定統一管理；`ai` 的測試所需套件（目前為 `jsonschema`、`pytest`）透過 Issue 提出。
