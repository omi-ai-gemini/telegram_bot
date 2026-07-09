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
from routes.thought import thought_bp
from routes.prompt_debug import prompt_debug_bp
from test_lab.db import init_test_lab_db
from test_lab.routes import test_lab_bp
from test_lab.service import should_skip_main_user_config
from service_center.handler import (
    handle_service_center_callback,
    handle_service_center_message,
    is_service_center_bot,
)
from service_center.telegram import setup_service_center_webhook
from service_center.db import init_service_center_db
from services.media_ai import (
    run_photo_message_in_thread,
    run_sticker_message_in_thread,
    run_unsupported_media_in_thread,
)
from service_center.telegram import send_message as send_service_center_message

#init_db()

app = Flask(__name__)

app.secret_key = SECRET_KEY
app.register_blueprint(admin_bp)
app.register_blueprint(setting_bp)
app.register_blueprint(thought_bp)
app.register_blueprint(prompt_debug_bp)
app.register_blueprint(test_lab_bp)

db_initialized = False

@app.before_request
def init_once():
    global db_initialized
    if not db_initialized:
        init_db()
        init_test_lab_db()
        init_service_center_db()

        # 服務中心 bot 使用環境變數 token，不進 DB。
        # 第一次 request 時自動把 webhook 接到 BASE_URL/webhook/<SERVICE_CENTER_BOT_ID>。
        try:
            setup_service_center_webhook()
        except Exception as exc:
            print("SERVICE CENTER WEBHOOK INIT ERROR:", exc, flush=True)

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

        # =========================
        # 服務中心 bot callback 分流
        # - 不進主遊戲 call_handler
        # - 不查 bot_config
        # - 不呼叫 Gemini
        # =========================
        if is_service_center_bot(bot_id):
            print(f"SERVICE CENTER CALLBACK RECEIVED bot_id={bot_id} user_id={user_id} chat_id={chat_id} data={user_text}", flush=True)
            handle_service_center_callback(
                user_id=user_id,
                bot_id=bot_id,
                chat_id=chat_id,
                message_id=message_id,
                callback_data=user_text,
                callback_id=callback_id,
            )
            return "ok"

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

    user_id = message["from"]["id"]
    chat_id = str(message["chat"]["id"])
    user_text = message.get("text", "")
    message_id = message.get("message_id")

    # =========================
    # 服務中心 bot 訊息分流
    # - 服務中心只處理文字 / callback
    # - 非文字至少要回覆，避免使用者傳了沒有反應
    # =========================
    if is_service_center_bot(bot_id):
        if "text" not in message:
            send_service_center_message(
                chat_id,
                "服務中心目前只能處理文字與按鈕操作。"
            )
            return "ok"

        print(f"SERVICE CENTER MESSAGE RECEIVED bot_id={bot_id} user_id={user_id} chat_id={chat_id} text={user_text}", flush=True)
        handle_service_center_message(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            user_text=user_text,
            message_id=message_id,
        )
        return "ok"

    # =========================
    # 自動保存 user_id
    # =========================
    # Prompt Test Lab 模式使用 test_profiles / test_sessions。
    # /test 相關訊息不寫入主遊戲 user_config，避免調教模組污染主遊戲帳號資料。
    if not should_skip_main_user_config(bot_id, chat_id, user_id, user_text):
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
    # 非文字訊息分流
    # - photo：Gemini 2.5 Flash 讀圖，再交回 3.1 Flash Lite 聊天流程回覆
    # - static sticker：3.1 Flash Lite 讀貼圖，再交回聊天流程回覆
    # - 其他目前不處理，但一定回覆防呆訊息
    # =========================
    if "photo" in message:
        run_photo_message_in_thread(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            message=message,
            message_id=message_id,
        )
        return "ok"

    if "sticker" in message:
        run_sticker_message_in_thread(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            message=message,
            message_id=message_id,
        )
        return "ok"

    if "text" not in message:
        run_unsupported_media_in_thread(bot_id, chat_id)
        return "ok"

    # =========================
    # 執行文字 AI
    # =========================
    threading.Thread(
        target=handle_message,
        args=(user_id, bot_id, chat_id, user_text, message_id),
        daemon=True,
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