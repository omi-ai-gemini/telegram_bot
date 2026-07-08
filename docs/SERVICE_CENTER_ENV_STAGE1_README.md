# Telemini 服務中心 Bot：環境變數 Token 版 Stage 1

這版只做服務中心 bot 的乾淨分流地基，不新增服務資料表。

## 目標

- 一隻固定服務中心 bot，所有使用者都可以使用。
- bot token 只放 Render 環境變數，不寫入 `bot_config`，不新增 `service_center_bots`。
- webhook 固定走 `/webhook/service_center`。
- main.py 在 webhook 入口先攔截服務中心 bot。
- 服務中心訊息不進主遊戲、不呼叫 Gemini、不寫聊天記憶、不寫 user_config。

## 新增 / 覆蓋檔案

新增：

```text
service_center/__init__.py
service_center/handler.py
service_center/telegram.py
service_center/db.py
```

覆蓋：

```text
config.py
main.py
handlers/message_handler.py
routes/admin.py
```

`service_center/db.py` 是刻意保留的 no-op 空殼，用來覆蓋舊 stage1 可能留下的建表版本；這版不會建立任何服務中心 bot table。

## Render 環境變數

```text
SERVICE_CENTER_BOT_ID=service_center
SERVICE_CENTER_BOT_TOKEN=BotFather 給你的服務中心 bot token
SERVICE_CENTER_ADMIN_IDS=你的 Telegram 數字 user_id，多人用逗號分隔
```

`SERVICE_CENTER_BOT_ID` 可以不填，預設就是：

```text
service_center
```

## 設定 webhook

部署後執行一次：

```powershell
$TOKEN="你的服務中心bot token"
$URL="https://你的-render網址/webhook/service_center"

Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/setWebhook?url=$URL"
```

成功後，服務中心 bot 的所有更新都會進：

```text
/webhook/service_center
```

## 分流行為

```text
Telegram 服務中心 bot
↓
/webhook/service_center
↓
main.py 判斷 is_service_center_bot(bot_id)
↓
service_center.handler
↓
直接 return ok
```

不會再往下走：

```text
handlers.message_handler
handlers.call_handler
services.call_ai
services.telegram_service
bot_config
chat_memory
user_config
Gemini
```

## 目前第一階段可用指令

```text
/start
/menu
/help
/manual
/說明
/status
```

目前按鈕只是骨架：

```text
📢 公告事項
🤖 建立Bot
🔑 Gemini API
📘 操作說明
📌 服務狀態
🛠 管理員
```

下一階段再把公告、建立遊戲 bot、Gemini API key、操作說明逐一接進來。
