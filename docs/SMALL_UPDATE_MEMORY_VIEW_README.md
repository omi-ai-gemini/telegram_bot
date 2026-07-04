# Telemini 小改版：重跑刪原訊息 / 記憶查看

## 更新內容

1. AI 回覆下方小按鈕縮短為：
   - ✏️
   - 🔁
   - ▶️

2. 按下「🔁 重跑」後會先刪除原本那則 AI 訊息，再重新發出新生成的訊息。

3. 使用者輸入 `/setting` 或 `/設定` 打開設定中心後，按「❌ 結束設定」會同時刪除：
   - 設定選單訊息
   - 使用者原本輸入的 `/setting` 或 `/設定`

4. 新增 `/memory` 與 `/記憶`：
   - 查看最近 10 筆短期記憶
   - 查看最近 6 筆摘要記憶
   - 打開既有重點記憶管理頁
   - 短期記憶與摘要記憶支援單筆刪除

## 新增資料表

部署後第一次請求會自動補：

```sql
setting_menu_sessions
```

用來記錄設定選單訊息與使用者 `/setting` 指令訊息的對應，方便退出時一起刪除。

## 修改檔案

- handlers/message_handler.py
- handlers/call_handler.py
- services/ai_actions.py
- services/commands.py
- services/database.py
- services/memory.py
- services/memory_summary.py
- services/memory_view.py
- services/setting_sessions.py
