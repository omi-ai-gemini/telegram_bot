# Service Center 自動接 Webhook 熱修

這包修正：服務中心 bot token 放環境變數後，程式會在第一次 request 時自動呼叫 Telegram `setWebhook`。

## 不新增 table

這版不會建立 `service_center_bots`，也不把服務中心 bot token 寫入 DB。

## 必填 Render 環境變數

```text
BASE_URL=https://你的-render網址
SERVICE_CENTER_BOT_ID=service_center
SERVICE_CENTER_BOT_TOKEN=BotFather 給你的服務中心 bot token
```

可選：

```text
SERVICE_CENTER_ADMIN_IDS=你的 Telegram 數字 ID
```

## 成功 log

部署後，只要 Render 被打到一次，例如健康檢查 `/` 或任一 webhook，Render Logs 應該出現：

```text
SERVICE CENTER WEBHOOK SET START url=https://.../webhook/service_center
SERVICE CENTER WEBHOOK SET OK url=https://.../webhook/service_center
```

使用者私訊服務中心 bot `/start` 後，應該出現：

```text
SERVICE CENTER MESSAGE RECEIVED bot_id=service_center ...
```

## 編譯

```bash
python -m py_compile main.py service_center/telegram.py service_center/handler.py service_center/db.py config.py
```
