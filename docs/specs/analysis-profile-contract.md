# 分析設定檔與分析設定追溯契約（A2-15）

> Schema：[`schemas/v1/analysis_profile.schema.json`](../../schemas/v1/analysis_profile.schema.json)、[`analysis_result.schema.json`](../../schemas/v1/analysis_result.schema.json) 的 `analysis_config`。版本 `1.0.0-draft.6`（Eric 2026-11-04 核准）。
> 參考檢查程式：`tests/contract/profile_check.py`（PF1–PF5、AR11）。

## 1. 目的

ExhibitIQ 不限定任何產業或 BXR 產品。使用者以「分析設定檔」（分析主題）決定這次要看什麼：分析模式、關鍵字（中英文與同義詞，可啟用／停用、可自訂分類）、企業關係訊號、評分權重。**新增或修改主題與關鍵字只修改資料，不修改核心程式、Schema 或重新部署前端程式碼。**

## 2. 分析模式

| `mode` | 名稱 | 需要 BXR 產品卡 | 評分 |
|---|---|---|---|
| `bxr_opportunity` | A. BXR 商機分析 | 使用（未核定時報告必須提示；`analysis_config.bxr_products_status`） | 設定 `score_model` 時才評分 |
| `industry_research` | B. 產業與技術研究 | **不得使用**（PF5、AR11） | 預設不評分 |
| `competitor_research` | C. 競爭對手研究 | **不得依賴**（PF5、AR11）；`targets` 指定企業或領域 | 設定 `score_model` 時才評分 |

同一個展覽可以用不同主題與模式重複分析；每次分析是一份新的分析結果（新的 `analysis_id`），彼此不覆蓋。

## 3. 設定檔

- 位置：`knowledge/analysis-profiles/<profile_id>.json`（「已提交」的設定）。`default-library` 是由分類詞草稿轉成的起始詞庫，只是起點。
- `version`：每次提交修改加 1。
- `keywords[]`：`term_id`、`category`（technology／product／application／industry／need／competitor 或自訂）、`label`、`label_en`、`synonyms`、`enabled`。
- `relationship_signals`：潛在客戶、競爭對手、合作夥伴、通路各自的訊號詞。**多標籤，不設優先順序；命中只是候選，不是事實。**
- `score_model`：選填，`weights` 是各因子的最高分數（整數）。

## 4. `profile_hash`

`"sha256:" + SHA-256(UTF-8(canonical JSON))`。canonical JSON：每一層物件的鍵依字母排序、分隔符號 `,` 與 `:`、不跳脫非 ASCII 字元。數值只用整數。瀏覽器與 Python 算出相同結果。

## 5. 分析結果的 `analysis_config`（AR11）

`profile_id`、`profile_version`、`profile_hash`、`mode`、`keywords_snapshot`（當次啟用的關鍵字完整快照）、選填 `score_model_id`、`bxr_products_status`。

| 規則 | 內容 |
|---|---|
| AR11 | 快照只含啟用的關鍵字且 `term_id` 不重複；沒有評分模型就不能有評分，有評分模型時所有評分都使用它；B、C 模式不使用 BXR 產品卡、不推薦 BXR 產品；A 模式必須寫明 `bxr_products_status`；倉庫中存在同 `profile_id` 同 `version` 的設定檔時，雜湊、模式與快照必須一致 |

沒有 `analysis_config` 的舊分析結果（draft.5）仍然有效。

## 6. 三種設定狀態與資料流（靜態網站不能執行分析）

```text
 Dashboard「分析設定」             GitHub（已提交）                    雲端分析（Claude Code 工作階段）           Dashboard
 ┌────────────────────┐  匯出 JSON   ┌──────────────────────────────┐  讀取設定檔 + 資料包     ┌───────────────────────────┐  bundle 重建
 │① 本機草稿          │ ───────────▶ │② knowledge/analysis-profiles/ │ ──────────────────────▶ │③ reports/analysis/…json    │ ───────────▶ 結果頁顯示
 │  瀏覽器持久化儲存   │  上傳／提交  │   <profile_id>.json（vN）     │  執行 Skill，save-analysis │  analysis_config 記錄 vN+hash│   使用的設定
 └────────────────────┘              └──────────────────────────────┘                          └───────────────────────────┘
```

1. **本機草稿：** 在 Dashboard 直接新增、編輯、刪除、啟用／停用關鍵字，建立、複製、重新命名、刪除主題，JSON 匯入／匯出。存在瀏覽器（localStorage），**只影響這台電腦的這個瀏覽器**，不會改變任何分析結果。
2. **已提交：** 要讓雲端分析使用某個主題時，匯出 JSON 並放到 `knowledge/analysis-profiles/`（GitHub 網頁上傳，或交給 Claude Code 工作階段提交）。網站重新建置後，該版本顯示為「已提交」。
3. **已產生分析結果：** 雲端的 Claude Code 工作階段（日後可改由 Actions）讀取已提交的設定檔與資料包執行分析，`save-analysis` 寫入 `reports/analysis/`，`analysis_config` 記錄設定版本與雜湊。

Dashboard 以雜湊比對三者並清楚標示：本機草稿與已提交版本不同時顯示「尚未提交，雲端分析不會使用」；每份分析結果顯示「使用設定 vN」。**前端不保存任何 Token，不直接寫入 GitHub，也不執行分析。**
