# ExhibitIQ Skill：安裝與使用（A2-03）

## 在 Claude Code 中使用
Claude Code 會讀取專案的 `.claude/skills/`。在雲端工作階段的 repo 根目錄執行一次：
```bash
mkdir -p .claude/skills && ln -sfn ../../skills/exhibitiq .claude/skills/exhibitiq
```
（`.claude/` 不提交到 Git；每個工作階段執行一次即可。）之後對 Claude Code 說「用 ExhibitIQ Skill 分析 <展覽>」，它會依 `SKILL.md` 執行。

## 輔助程式（不使用 AI，只做固定步驟）
```bash
T=skills/exhibitiq/scripts/exhibitiq_tools.py
python $T list                                      # 已登錄展覽與最新資料包
python $T select <exhibition_id> [年份]             # 選出最新、驗證通過的資料包
python $T check-all                                 # 批次檢查所有最新資料包（版本、雜湊、驗證）
python $T validate-package <package_dir>            # 分析前必做
python $T validate-analysis <analysis.json> <package_dir>   # 發布前必做
python $T save-analysis <analysis.json> <package_dir>       # 驗證通過才寫入 reports/analysis/<input_dataset_id>/<analysis_id>.json；已存檔的結果不能修改（只能更新審核欄位），重新分析要用新的 analysis_id
python $T report <analysis.json> <package_dir> > <analysis_id>.md
```
- 資料集索引預設讀 `data/index/datasets.json`，不存在時使用範例；可用 `--index` 指定。
- `validate-package` 在 `etl.validate`（資料工程）可匯入時使用它；Phase 1 整合前改用契約參考檢查，並在輸出註明。
- 沒有可用資料包的展覽（例如取得失敗），`select` 會回報原因並以代碼 2 結束，**不會勉強分析**。

## 範例（黃金樣本，合成資料）
```bash
G=data/samples/golden/v1
python $T select golden-fair --index $G/dataset_index.json
python $T validate-analysis $G/expected/analysis/analysis_result.json $G/package
python $T report $G/expected/analysis/analysis_result.json $G/package
```

## 可重現性檢查（A3-08）

```bash
python skills/exhibitiq/scripts/repro_check.py --check
```

在任何乾淨的雲端工作區（Eric 或 Albert 的）執行，所有確定性指令（`validate-package`、`classify`、`relate`、`score`、`config`、`compare`、`report`）的輸出雜湊都必須等於 `skills/exhibitiq/repro/expected-digest.json`。有意修改輸出時，執行 `python skills/exhibitiq/scripts/repro_check.py > skills/exhibitiq/repro/expected-digest.json` 更新並在 PR 說明原因。AI 撰寫的結論本身不是確定性的；可重現的是輸入、工具輸出與驗證規則。
