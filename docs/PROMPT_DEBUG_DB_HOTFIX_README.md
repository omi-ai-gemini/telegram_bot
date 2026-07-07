# Prompt Debug DB 熱修

## 修正問題

Render log：

```text
psycopg2.errors.UndefinedColumn: column "action_id" does not exist
```

原因：舊版聊天室 prompt_debug 已經建立過 `prompt_debug_logs`，新版網頁版 `CREATE TABLE IF NOT EXISTS` 不會自動補新欄位，導致後面建立 `idx_prompt_debug_logs_action` 索引時找不到 `action_id`，整個 `init_db()` 失敗。

## 修正內容

只修改：

- `services/database.py`

在建立 prompt_debug 索引前新增 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`，補齊新版網頁版需要的欄位。

## 部署後

第一次 request 會自動補欄位，不需要清 DB，不會刪 prompt_debug 舊資料。
