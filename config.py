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


# =========================
# AI Horde 圖片生成
# =========================
AI_HORDE_API_KEY_1 = os.getenv("AI_HORDE_API_KEY_1")
AI_HORDE_API_KEY_2 = os.getenv("AI_HORDE_API_KEY_2")
AI_HORDE_MODEL = os.getenv("AI_HORDE_MODEL", "Flux.1-Schnell fp8 (Compact)")
AI_HORDE_ALLOW_NSFW = os.getenv("AI_HORDE_ALLOW_NSFW", "true")
# =========================
# Ollama / Qwen 副模型
# =========================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_DEPUTY_MODEL = os.getenv("OLLAMA_DEPUTY_MODEL", "qwen2.5:7b")
OLLAMA_PROMPT_MODEL = os.getenv("OLLAMA_PROMPT_MODEL", OLLAMA_DEPUTY_MODEL)
OLLAMA_TIMEOUT_SECONDS = _env_int("OLLAMA_TIMEOUT_SECONDS", 180)
OLLAMA_CHAT_NUM_PREDICT = _env_int("OLLAMA_CHAT_NUM_PREDICT", 512)
OLLAMA_PROMPT_NUM_PREDICT = _env_int("OLLAMA_PROMPT_NUM_PREDICT", 700)

# =========================
# ComfyUI 文生圖
# =========================
COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
COMFYUI_TIMEOUT_SECONDS = _env_int("COMFYUI_TIMEOUT_SECONDS", 900)
COMFYUI_POLL_SECONDS = _env_int("COMFYUI_POLL_SECONDS", 2)
COMFYUI_CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "cyberrealisticXL_v100.safetensors")
COMFYUI_UPSCALE_MODEL = os.getenv("COMFYUI_UPSCALE_MODEL", "RealESRGAN_x2plus.pth")
COMFYUI_FACE_DETECTOR = os.getenv("COMFYUI_FACE_DETECTOR", "bbox/face_yolov8m.pt")
COMFYUI_WIDTH = _env_int("COMFYUI_WIDTH", 768)
COMFYUI_HEIGHT = _env_int("COMFYUI_HEIGHT", 1024)

# =========================
# Render → 本機 AI 隱私閘道
# =========================
# 正式部署在 Render 時使用 HTTPS Tunnel 網址；本機整合測試可留空。
LOCAL_AI_GATEWAY_URL = os.getenv("LOCAL_AI_GATEWAY_URL", "")
LOCAL_AI_GATEWAY_SECRET = os.getenv("LOCAL_AI_GATEWAY_SECRET", "")
LOCAL_AI_GATEWAY_TIMEOUT_SECONDS = _env_int("LOCAL_AI_GATEWAY_TIMEOUT_SECONDS", 180)
# 有套 Cloudflare Access Service Token 時才需要填。
CF_ACCESS_CLIENT_ID = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")
# Telemini 與 ComfyUI 同機執行時，用於讀完 PreviewImage 後刪除 temp。
COMFYUI_TEMP_DIR = os.getenv("COMFYUI_TEMP_DIR", "")
COMFYUI_ROOT = os.getenv("COMFYUI_ROOT", "")

