import os

# =========================
# Gemini
# =========================

GEMINI_MODEL = "gemini-3.1-flash-lite"

# 如果你未來想保留預設備用KEY才留著
#DEFAULT_GEMINI_KEY = os.getenv("DEFAULT_GEMINI_KEY")

# =========================
# Telegram
# =========================

TELEGRAM_API_BASE = "https://api.telegram.org"

# =========================
# Database
# =========================

#DB_NAME = "app.db"

# =========================
# AI參數
# =========================

#MAX_OUTPUT_TOKENS = 1024   #最大TOKEN
#TEMPERATURE = 0.8  #創意度

# =========================
# Debug
# =========================

#DEBUG = False

# =========================
# 環境變數
# =========================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
# =========================
# Setting page signed URLs
# =========================
SETTING_LINK_SECRET = os.getenv("SETTING_LINK_SECRET")
# =========================
# Service Center Bot
# =========================
# 系統級服務中心 bot：token 只放環境變數，不進 DB。
# webhook 建議固定設為：BASE_URL/webhook/service_center
SERVICE_CENTER_BOT_ID = os.getenv("SERVICE_CENTER_BOT_ID", "service_center")
SERVICE_CENTER_BOT_TOKEN = os.getenv("SERVICE_CENTER_BOT_TOKEN")
SERVICE_CENTER_ADMIN_IDS = os.getenv("SERVICE_CENTER_ADMIN_IDS", "")

