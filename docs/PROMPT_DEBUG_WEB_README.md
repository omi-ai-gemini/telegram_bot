# Telemini Prompt Debug 網頁版

## 目的

開發者除錯用：每次主遊戲呼叫 Gemini 前，保存實際送進 `contents=prompt` 的完整 prompt。

這版不再把長 prompt 丟回 Telegram 聊天室，避免手機 App 因大量文字閃退。

## 指令

```text
/prompt_debug
/prompt
/提示除錯
```

送出 Prompt Debug 網頁入口。

```text
/prompt_debug_compare
/prompt_compare
/提示比對
```

送出最近兩筆 prompt 的比對頁入口。

## 網頁

```text
/prompt_debug?token=...
/prompt_debug/<id>?token=...
/prompt_debug/compare?token=...
```

網址使用短效簽章 token，預設 30 分鐘有效。

## 保存範圍

目前會記錄：

- 一般新輸入回覆
- /reply 或 🗣️ 救援回覆
- 🔁 重跑
- ▶️ 接續

## DB

新增資料表：

```text
prompt_debug_logs
```

每個 `bot_id + chat_id` 只保留最新 50 筆。

## 注意

Prompt Debug 會保存解密後、組裝完成的完整 prompt，包含短期記憶、長期摘要、重點記憶、人物設定與自訂風格。只給開發者使用，不要公開連結。
