import os
import google.generativeai as genai

# =========================
# 環境變數（Render + GitHub部署）
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# =========================
# Gemini初始化
# =========================

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    "gemini-3.1-flash-Lite"
    )
