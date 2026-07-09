Telemini 最新服務中心檔案包

覆蓋檔案：
- config.py
- main.py
- service_center/__init__.py
- service_center/db.py
- service_center/handler.py
- service_center/telegram.py

附帶說明文件：
- docs/SERVICE_CENTER_ENV_STAGE1_README.md
- docs/SERVICE_CENTER_AUTOWEBHOOK_HOTFIX_README.md
- docs/SERVICE_CENTER_BUTTONS_README.md

Render 必填環境變數：
- BASE_URL=https://你的-render網址
- SERVICE_CENTER_BOT_ID=service_center
- SERVICE_CENTER_BOT_TOKEN=BotFather 給你的服務中心 bot token

可選：
- SERVICE_CENTER_ADMIN_IDS=你的 Telegram 數字 ID，多人用逗號分隔

部署後：
- 第一次 request 會自動設定服務中心 webhook。
- webhook 路徑：/webhook/service_center
- 服務中心 bot 不進主遊戲、不呼叫 Gemini、不寫 chat_memory、不查 bot_config。

測試：
python -m py_compile main.py config.py service_center/handler.py service_center/telegram.py service_center/db.py
