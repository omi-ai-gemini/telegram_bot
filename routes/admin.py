from flask import render_template, request, session, redirect, Blueprint
from config import ADMIN_PASSWORD
import os

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

@admin_bp.route("/admin/manual")
def admin_manual():
    return render_template("manual.html")

# =========================
# admin後台網站
# =========================

#後台首頁
@admin_bp.route("/admin/login/developer")
def admin_login_developer():

    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template("developer.html")