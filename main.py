from flask import Flask, request
from flask import render_template
import os
import threading
from handlers.message_handler import run_ai
from services.memory import add_chat
from services.database import init_db
from services.database import get_conn
from services.bot_router import get_bot_token

init_db()

app = Flask(__name__)

# =========================
# Webhook（核心入口）
# =========================
@app.route("/webhook/<bot_id>", methods=["POST"])
def webhook(bot_id):

    data = request.json

    # =========================
    # 解析json
    # =========================
    if not data or "message" not in data:
        return "ok"

    message = data["message"]

    if "text" not in message:
        return "ok"
    
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    user_text = message["text"]

    # =========================
    # 自動保存user_id
    # =========================
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO user_config (user_id, gemini_key)
    VALUES (?, NULL)
    """, (user_id,))

    conn.commit()
    conn.close()

    print("DEBUG bot_id:", bot_id)
    print("DEBUG token:", get_bot_token(bot_id))

    # =========================
    # 執行AI
    # =========================
    add_chat(chat_id, "user", user_text)

    # 🚀 直接丟背景跑 AI（避免 timeout）
    threading.Thread(
        target=run_ai,
        args=(user_id, bot_id, chat_id, user_text)
    ).start()

    return "ok"

# =========================
# 健康檢查（Render用）
# =========================
@app.route("/")
def home():
    return "OK"

# =========================
# admin後台網站
# =========================
@app.route("/admin")
def admin():
    return render_template("admin.html")

# =========================
# 啟動
# =========================
if __name__ == "__main__":

    port = int(os.environ["PORT"])
    app.run(host="0.0.0.0", port=port)