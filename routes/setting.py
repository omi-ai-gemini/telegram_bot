from flask import Blueprint, request, render_template, jsonify
from services.character import get_character_settings, update_character_settings

setting_bp = Blueprint("setting", __name__)


# =========================
# 劇本設定表單頁入口
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

    # =========================
    # 先讀取目前設定
    # 用來保留 mode，避免儲存表單時把模式重置
    # =========================
    current_settings = get_character_settings(bot_id, chat_id)

    settings = {
        "mode": current_settings.get("mode", "聊天模式"),

        # AI 設定：必填
        "ai_name": request.form.get("ai_name", "").strip(),
        "ai_gender": request.form.get("ai_gender", "").strip(),
        "ai_appearance": request.form.get("ai_appearance", "").strip(),
        "story_background": request.form.get("story_background", "").strip(),
        "ai_opening": request.form.get("ai_opening", "").strip(),

        # 使用者設定：選填
        "user_gender": request.form.get("user_gender", "").strip(),
        "user_appearance": request.form.get("user_appearance", "").strip(),
        "user_other_settings": request.form.get("user_other_settings", "").strip()
    }

    # =========================
    # 後端必填驗證
    # 前端 required 可以被繞過，所以後端一定也要檢查
    # =========================
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