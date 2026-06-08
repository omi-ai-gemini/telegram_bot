from flask import Flask, request
import threading
from handlers.message_handler import run_ai

app = Flask(__name__)

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

    # 🚀 直接丟背景跑 AI（避免 timeout）
    threading.Thread(
        target=run_ai,
        args=(chat_id, user_text)
    ).start()

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