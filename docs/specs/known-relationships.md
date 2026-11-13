# 已知企業關係名單（人工標準樣本）規格

> A3-07｜負責人：專案負責人（`ai`）｜名單由 Eric 於 2026-11-09 提供（原訂由 Albert 提供，Issue #90）

## 1. 用途

名單是**人工標準答案**，用來檢查 AI 初篩的企業關係（`relate`）有沒有找到已知的競爭同行、合作夥伴、通路與潛在客戶。名單**不是**完整答案：不在名單上的 AI 候選企業只能列為「名單未列」，不能算成錯誤。

## 2. 檔案位置與格式

- **位置：** `knowledge/benchmarks/known-competitors.csv`（Eric 2026-11-09 提供，整理自公司內部競品簡報：19 筆，含補充競品 Ikramatic；簡報判定「非直接競爭」的 Shooting-Soft 不列入）。合成範例：`data/golden/v1/known/known-relationships.csv`。
- **編碼：** UTF-8，可以有 BOM（Excel「CSV UTF-8」存檔即可）；逗號分隔；第一列是欄位名稱。
- **欄位（順序不限，名稱要一致）：**

| 欄位 | 必填 | 說明 |
|---|---|---|
| `company_name` | 是 | 企業名稱，盡量使用官方名稱（中文或英文） |
| `aliases` | 否 | 別名，用 `;` 分隔，例如英文名、簡稱、舊名 |
| `country` | 否 | 國家或地區 |
| `website` | 否 | 官網網址；用網域比對，有填比對率較高 |
| `relationship` | 是 | `competitor`／`partner`／`channel`／`potential_customer`；同時屬於多種關係時用 `;` 分隔 |
| `source` | 是 | 判斷依據，例如：「Albert 提供（公司內部認知）」、官網網址、新聞連結 |
| `notes` | 否 | 備註 |

**範例：**

```csv
company_name,aliases,country,website,relationship,source,notes
Example Simulation Co.,Example Sim;範例模擬,TW,https://www.example.com,competitor,Albert 提供（公司內部認知）,
Another Corp,,US,,partner;channel,https://news.example.com/123,曾共同參展
```

## 3. 規則

1. **只放可以公開的內容**：repo 是公開的。密碼、Token、金鑰、客戶機密、報價、內部評語一律不放。
2. **不推測、不補資料**：原始資料沒有的欄位留空，不要自己查或猜國家、官網或別名。看不出關係類型時，問 Albert，不要猜。
3. 每一列都要有 `source`；不知道出處時寫「Albert 提供（公司內部認知）」。
4. 同一家企業只列一次（名稱比對不分大小寫、忽略空白與標點）。

## 4. 驗證與使用

```bash
python skills/exhibitiq/scripts/exhibitiq_tools.py validate-known knowledge/benchmarks/known-competitors.csv
python skills/exhibitiq/scripts/exhibitiq_tools.py benchmark knowledge/benchmarks/known-competitors.csv <資料包目錄> --profile <分析設定>
```

- `validate-known`：檢查欄位、關係類型、必填與重複；`ok: false` 時列出每一列的問題（exit 1）。
- `benchmark`：用企業名稱、別名（比對資料包的名稱、英文名、中文名與別名）或官網網域，找出名單企業在資料包中的 `company_id`，再和 `relate` 的候選關係比對。**不做模糊比對**：名稱不同又沒有網址時視為不在資料包中。
- 輸出：每種關係的名單家數、在資料包中的家數、AI 找到的家數、召回率（沒有可比對的企業時為 `null`，不給數字）；每一列的找到／遺漏／其他候選；名單未列的候選企業（無法判斷對錯）。資料包不完整時，名單企業沒有出現可能只是尚未取得。
