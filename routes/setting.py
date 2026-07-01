from flask import Blueprint, request, render_template, jsonify
from services.character import (
    get_character_mode,
    get_character_settings,
    update_character_settings
)
from services.chat_persona import (
    get_chat_persona_settings,
    update_chat_persona_settings
)

setting_bp = Blueprint("setting", __name__)


# =========================
# 人物 / 劇本設定分流入口
# 聊天模式 → 聊天人物表單
# 劇場模式 → 劇本表單
# =========================
@setting_bp.route("/setting/persona", methods=["GET"])
def persona_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")

    if not bot_id or not chat_id:
        return "缺少 bot_id 或 chat_id", 400

    mode = get_character_mode(bot_id, chat_id)

    # =========================
    # 劇場模式 → 原本劇本表單
    # =========================
    if mode == "劇場模式":

        settings = get_character_settings(bot_id, chat_id)

        return render_template(
            "character_form.html",
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            settings=settings
        )

    # =========================
    # 聊天模式 → 新聊天人物表單
    # =========================
    settings = get_chat_persona_settings(bot_id, chat_id)

    return render_template(
        "chat_persona_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        settings=settings
    )


# =========================
# 舊劇本設定表單入口
# 保留，避免舊網址不能用
# =========================
@setting_bp.route("/setting/character", methods=["GET"])
def character_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")

    settings = get_character_settings(bot_id, chat_id)

    return render_template(
        "character_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        settings=settings
    )


# =========================
# 儲存聊天模式人物設定
# 不必填，允許全部空白
# =========================
@setting_bp.route("/setting/chat_persona/save", methods=["POST"])
def save_chat_persona_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()

    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    settings = {
        "persona_name": request.form.get("persona_name", "").strip(),
        "persona_gender": request.form.get("persona_gender", "").strip(),
        "persona_background": request.form.get("persona_background", "").strip()
    }

    update_chat_persona_settings(bot_id, chat_id, settings)

    return jsonify({
        "ok": True,
        "message": "聊天人物設定已儲存，可以關閉此頁。"
    })


# =========================
# 儲存劇本設定
# =========================
@setting_bp.route("/setting/character/save", methods=["POST"])
def save_character_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()

    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    current_settings = get_character_settings(bot_id, chat_id)

    settings = {
        "mode": current_settings.get("mode", "聊天模式"),

        "ai_name": request.form.get("ai_name", "").strip(),
        "ai_gender": request.form.get("ai_gender", "").strip(),
        "ai_appearance": request.form.get("ai_appearance", "").strip(),
        "story_background": request.form.get("story_background", "").strip(),
        "ai_opening": request.form.get("ai_opening", "").strip(),

        "user_gender": request.form.get("user_gender", "").strip(),
        "user_appearance": request.form.get("user_appearance", "").strip(),
        "user_other_settings": request.form.get("user_other_settings", "").strip()
    }

    required_fields = {
        "ai_name": "AI姓名",
        "ai_gender": "AI性別",
        "ai_appearance": "AI形象",
        "story_background": "故事背景",
        "ai_opening": "AI開場白"
    }

    missing_fields = []

    for key, label in required_fields.items():
        if not settings[key]:
            missing_fields.append(label)

    if missing_fields:
        return jsonify({
            "ok": False,
            "message": "以下欄位必填：" + "、".join(missing_fields)
        }), 400

    update_character_settings(bot_id, chat_id, settings)

    return jsonify({
        "ok": True,
        "message": "劇本設定已儲存，可以關閉此頁。"
    })
