from flask import Flask, request
import os
import threading
from handlers.message_handler import handle_message
from handlers.call_handler import handle_ui
from services.database import init_db
from services.database import get_conn
from config import SECRET_KEY
from routes.admin import admin_bp
from routes.setting import setting_bp

#init_db()

app = Flask(__name__)

app.secret_key = SECRET_KEY
app.register_blueprint(admin_bp)
app.register_blueprint(setting_bp)

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

    if not data:
        return "ok"

    # =========================
    # callback_query
    # =========================
    if "callback_query" in data:

        callback = data["callback_query"]

        callback_id = callback["id"]
        user_id = callback["from"]["id"]
        chat_id = str(callback["message"]["chat"]["id"])
        message_id = callback["message"]["message_id"]
        user_text = callback["data"]

        # 注意：
        # 不在 main.py 先 answer_callback_query
        # 交給 call_handler 控制提示文字
        handle_ui(
            user_id,
            bot_id,
            chat_id,
            message_id,
            user_text,
            callback_id
        )

        return "ok"

    # =========================
    # 解析 message
    # =========================
    if not data or "message" not in data:
        return "ok"

    message = data["message"]

    if "text" not in message:
        return "ok"
    
    user_id = message["from"]["id"]
    chat_id = str(message["chat"]["id"])
    user_text = message["text"]
    message_id = message.get("message_id")

    # =========================
    # 自動保存 user_id
    # =========================
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO user_config (user_id, gemini_key)
    VALUES (%s, %s)
    ON CONFLICT (user_id) DO NOTHING
    """, (
        str(user_id),
        None
    ))

    conn.commit()
    conn.close()

    print("DEBUG bot_id:", bot_id)

    # =========================
    # 執行 AI
    # =========================
    threading.Thread(
        target=handle_message,
        args=(user_id, bot_id, chat_id, user_text, message_id)
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