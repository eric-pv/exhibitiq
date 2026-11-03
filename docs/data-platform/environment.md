# 資料工程雲端 Python 環境

> Issue：P1-DATA-01（#6）｜負責人：data｜路徑歸屬：`docs/data-platform/`（data）
> 本文件只記錄實際執行過的結果；未驗證的項目明確列在「未驗證」。

## 檔案

| 檔案 | 用途 |
|---|---|
| `requirements.txt` | 依賴清單，固定版本（`==`）。依賴以此檔為唯一來源 |
| `pyproject.toml` | 專案中繼資料（`requires-python = ">=3.11"`）與 pytest 設定（只跑 `tests/data`） |
| `.devcontainer/devcontainer.json` | Codespaces 工作區設定：Python 3.12 映像檔，建立後自動 `pip install -r requirements.txt` |
| `tests/data/test_environment_smoke.py` | 環境 smoke test |

## 在雲端建立環境與執行測試

在 Codespaces 或任何雲端終端機，於 repo 根目錄：

```bash
python3 -m venv .venv          # Codespaces 以 devcontainer 建立時可略過
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/data
```

預期結果：`4 passed`。

## 已驗證（2026-11-03，雲端 Linux 容器）

用 `python -m venv` 建立全新環境，只以 `requirements.txt` 安裝，再執行 `pytest tests/data`：

| Python | pytest | jsonschema | 結果 |
|---|---|---|---|
| 3.11.18 | 9.2.0 | 4.26.0 | 4 passed |
| 3.12.3 | 9.2.0 | 4.26.0 | 4 passed |
| 3.13.18 | 9.2.0 | 4.26.0 | 4 passed |

反向驗證：把 `requirements.txt` 的 `jsonschema` 改成 `4.0.0` 後，`test_requirements_are_exact_pins_and_installed` 失敗；還原後 4 passed。

Smoke test 檢查四件事：Python 版本不低於 3.11；`pyproject.toml` 的 `requires-python` 與 pytest 路徑設定；`requirements.txt` 每一行都是精確版本且與已安裝版本相同；`jsonschema` 支援 Draft 2020-12（版本政策規定的格式）。

## 版本選擇依據

- `requires-python >= 3.11`：3.11、3.12、3.13 都實測通過。
- Devcontainer 與日後 GitHub Actions 建議統一使用 **3.12**：這是上表中間版本，且 `requirements.txt` 的版本就是在 3.12.3 解析的。
- 2026-11-03 查看專案的 Codespace，預設 Python 為 3.14.2。3.14 **未**在本 Issue 測試，所以不列入支援範圍。

## 未驗證

- **`.devcontainer/` 尚未實際建置。** 映像檔 `mcr.microsoft.com/devcontainers/python:3.12` 與 `postCreateCommand` 沒有在 Codespaces 重建驗證。第一次用它開 Codespace 時，請確認 `python3 --version` 是 3.12.x，且 `pytest tests/data` 為 4 passed；若失敗，請開 Issue 回報。
- **Python 3.14** 未測試。
- **GitHub Actions** 尚未設定，屬 P1-DATA-07；本 Issue 不建立 workflow。
- **Claude Code 不在 Codespace 內安裝。** 2026-11-03 在該 Codespace 執行 `claude --version` 找不到指令，本設定也沒有安裝它；Claude Code 在另一個雲端工作階段執行，開發結果透過 GitHub 分支與 PR 交付。
- 只固定頂層套件。`jsonschema` 的相依套件（`attrs`、`referencing`、`rpds-py` 等）未固定，版本由 pip 解析；需要完全可重現的鎖定檔時，另開 Issue。

## 新增依賴的規則

只加入該 Issue 確實用到的套件，精確固定版本，並更新本文件的已驗證表。不得在 `etl/`、`crawler/`、`tests/data/` 內另外定義 Schema 或欄位清單；資料契約只在 `schemas/`。
