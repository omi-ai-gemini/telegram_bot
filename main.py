from flask import Flask, request
import os
import requests
import google.generativeai as genai

app = Flask(__name__)

# =========================
# 環境變數（Render + GitHub部署）
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Gemini初始化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# =========================
# Telegram 發送訊息
# =========================
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


# =========================
# Webhook（核心入口）
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    # 只處理文字訊息
    if "message" not in data:
        return "ok"

    message = data["message"]

    if "text" not in message:
        return "ok"

    chat_id = message["chat"]["id"]
    user_text = message["text"]

    # =========================
    # AI 回覆
    # =========================
    response = model.generate_content(user_text)
    reply = response.text

    # =========================
    # 回傳 Telegram
    # =========================
    send_message(chat_id, reply)

    return "ok"


# =========================
# 健康檢查（Render用）
# =========================
@app.route("/")
def home():
    return "OK"


# =========================
# 啟動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)