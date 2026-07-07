# Telemini Prompt Debug 外帶說明

## 功能

新增開發者用 prompt dump：

- 每次主遊戲呼叫 Gemini 前，把實際送入 `contents=prompt` 的完整 prompt 存進 DB。
- 不把 prompt 明文印到 Render log。
- 每個 `bot_id + chat_id` 最多保留最新 30 筆，避免資料庫膨脹。
- 可從 Telegram 用指令查看。

## 指令

```text
/prompt_debug
```

查看目前聊天室最新一筆完整 prompt。

```text
/prompt_debug_list
```

列出目前聊天室最近 10 筆 prompt debug 紀錄。

```text
/prompt_debug 123
```

查看指定 id 的完整 prompt。

## 新增資料表

```sql
prompt_debug_logs
```

部署後第一次請求會由 `init_db()` 自動建立。

## 覆蓋 / 新增檔案

- `services/database.py`
- `services/gemini_service.py`
- `services/call_ai.py`
- `services/ai_actions.py`
- `handlers/message_handler.py`
- `services/prompt_debug.py`
- `docs/PROMPT_DEBUG_README.md`

## 注意

prompt 內可能包含短期記憶、長期摘要、重點記憶、人物設定、聊天人物設定、自訂風格與使用者最新輸入。
這是開發者除錯功能，不要公開給一般使用者。
