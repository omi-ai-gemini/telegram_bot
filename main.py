from flask import Flask, request, render_template, redirect, session
import os
import threading
from handlers.message_handler import run_ai
from services.memory import add_chat
from services.database import init_db
from services.database import get_conn
from config import ADMIN_PASSWORD
from config import SECRET_KEY

init_db()

app = Flask(__name__)

app.secret_key = SECRET_KEY

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

#首頁
@app.route("/admin")
def admin():
    return render_template("index.html")

#登入畫面
@app.route("/admin/login")
def admin_login():
    return render_template("login.html")

#登入GET
@app.route("/admin/login", methods=["GET"])
def admin_login():
    return render_template("login.html")

#登入POST
@app.route("/admin/login", methods=["POST"])
def admin_login_post():
    
    password = request.form["password"]

    if password == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect("/admin")
    
    return "密碼錯誤"

#後台主頁
@app.route("/admin/login/developer")
def admin_login_developer():

    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template("developer.html")

# =========================
# 啟動
# =========================
if __name__ == "__main__":

    port = int(os.environ["PORT"])
    app.run(host="0.0.0.0", port=port)