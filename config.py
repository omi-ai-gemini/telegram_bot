import os

# =========================
# Gemini
# =========================

GEMINI_MODEL = "gemini-3.1-flash-lite"

# 圖片解析專用模型：只把圖片轉成文字描述，再交回主模型回覆。
# 先用 3.5 Flash；若遇到 quota / rate limit / service unavailable，會在 gemini_service.py 自動切到 3 Flash Preview。
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash")
GEMINI_VISION_FALLBACK_MODEL = os.getenv("GEMINI_VISION_FALLBACK_MODEL", "gemini-3-flash-preview")

def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)

# 圖片解析單次輸出上限：盡量拉高，避免過度保守截斷。
GEMINI_VISION_MAX_OUTPUT_TOKENS = _env_int("GEMINI_VISION_MAX_OUTPUT_TOKENS", 65536)
# 靜態貼圖維持較小上限，避免不必要的額度消耗。
GEMINI_STICKER_MAX_OUTPUT_TOKENS = _env_int("GEMINI_STICKER_MAX_OUTPUT_TOKENS", 500)

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

