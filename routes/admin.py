from flask import render_template, request, session, redirect, Blueprint
from config import ADMIN_PASSWORD
import os
import requests
from services.database import save_bot, update_gemini_key

admin_bp = Blueprint("admin", __name__)

#ADMIN_PASSWORD = os.getenv("ADMIN_PADDWORD")

# =========================
# admin首頁網站
# =========================

#首頁
@admin_bp.route("/admin")
def admin():
    return render_template("index.html")

#登入畫面
#@admin_bp.route("/admin/login")
#def admin_login():
#    return render_template("login.html")

#登入GET
@admin_bp.route("/admin/login", methods=["GET"])
def admin_login():
    return render_template("login.html")

#登入POST
@admin_bp.route("/admin/login", methods=["POST"])
def admin_login_post():
    
    password = request.form["password"]

    if password == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect("/admin/developer")
    
    return "密碼錯誤"

# =========================
# admin說明網站
# =========================

@admin_bp.route("/admin/manual", methods=["GET"])
def admin_manual():
    return render_template("manual.html")


# setwebhook
@admin_bp.route("/admin/manual/add_bot", methods=["POST"])
def add_bot_route():

    bot_id = request.form["bot_id"]
    token = request.form["token"]

    #DB
    save_bot(bot_id, token)

    #webhook
    base_url = os.getenv("BASE_URL")
    webhook_url = f"{base_url}/webhook/{bot_id}"

    telegram_api = f"https://api.telegram.org/bot{token}/setWebhook"

    res = requests.get(telegram_api, params={"url": webhook_url})

    if res.ok:
        return "webhook設定成功"
    
    return res.text

@admin_bp.route("/admin/manual/add_key", methods=["POST"])
def add_key_route():

    user_id = request.form["user_id"]
    gemini_api_key = request.form["gemini_api_key"]

    #DB
    update_gemini_key(user_id, gemini_api_key)

    return "gemini api 設定成功"


# =========================
# admin後台網站
# =========================

#後台首頁
@admin_bp.route("/admin/login/developer")
def admin_login_developer():

    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template("developer.html")
