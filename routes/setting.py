from flask import Blueprint, request, render_template

setting_bp = Blueprint("setting", __name__)


# =========================
# 劇本設定表單頁入口
# =========================
@setting_bp.route("/setting/character", methods=["GET"])
def character_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")

    return render_template(
        "character_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id
    )