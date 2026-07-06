from flask import Blueprint, redirect, render_template, request

from test_lab.service import (
    get_profile,
    save_profile_settings,
    verify_page_token,
)


test_lab_bp = Blueprint("test_lab", __name__, template_folder="templates")


@test_lab_bp.route("/test_lab", methods=["GET"])
def test_lab_page():
    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")
    token = request.args.get("token", "")

    if not verify_page_token(bot_id, chat_id, user_id, token):
        return "test_lab 設定連結驗證失敗或已過期", 403

    profile = get_profile(bot_id, user_id)
    return render_template(
        "test_lab_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        token=token,
        profile=profile,
    )


@test_lab_bp.route("/test_lab/save", methods=["POST"])
def save_test_lab_page():
    bot_id = request.form.get("bot_id", "")
    chat_id = request.form.get("chat_id", "")
    user_id = request.form.get("user_id", "")
    token = request.form.get("token", "")

    if not verify_page_token(bot_id, chat_id, user_id, token):
        return "test_lab 設定連結驗證失敗或已過期", 403

    save_profile_settings(bot_id, user_id, request.form)
    return redirect(f"/test_lab?bot_id={bot_id}&chat_id={chat_id}&user_id={user_id}&token={token}")
