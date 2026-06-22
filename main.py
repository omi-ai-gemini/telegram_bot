from flask import Flask, request
import os
import threading
from handlers.message_handler import run_ai
from services.memory import add_chat
from services.database import init_db
from services.database import get_conn
from config import SECRET_KEY
from routes.admin import admin_bp

#init_db()

app = Flask(__name__)

app.secret_key = SECRET_KEY
app.register_blueprint(admin_bp)

db_initialized = False

@app.before_request
def init_once():
    global db_initialized
    if not db_initialized:
        init_db()
        db_initialized = True

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
    chat_id = str(message["chat"]["id"])
    user_text = message["text"]

    # =========================
    # 自動保存user_id
    # =========================
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO user_config (user_id, gemini_key)
    VALUES (%s, %s)
    ON CONFLICT (user_id) DO NOTHING
    """, (str(user_id), None))

    conn.commit()
    conn.close()

    print("DEBUG bot_id:", bot_id)
    #print("DEBUG token:", get_bot_token(bot_id))

    # =========================
    # 執行AI
    # =========================
    add_chat(bot_id, chat_id, "user", user_text)

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
# 啟動
# =========================
if __name__ == "__main__":

    port = int(os.environ["PORT"])
    app.run(host="0.0.0.0", port=port)