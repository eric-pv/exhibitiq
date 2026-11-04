# 來源設定目錄

每個檔案 `<名稱>.toml` 描述一個來源（格式見 `docs/data-platform/run-logging-and-errors.md` 與 `crawler-framework.md`）。
`name` 必須等於檔名。展覽之間的差異只放在這裡與適配器；核心程式不得出現特定展覽。
新增來源前先做來源評估；是否排程由 `crawler/schedule.toml` 決定，不是此目錄。
