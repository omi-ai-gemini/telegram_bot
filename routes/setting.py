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
from services.reply_style import (
    get_reply_style_settings,
    update_reply_style_settings,
    normalize_style_type
)
from services.style import (
    DEFAULT_CHAT_REPLY_STYLE,
    DEFAULT_THEATER_REPLY_STYLE
)
from services.memory import (
    add_important_fact,
    list_important_facts,
    update_important_fact,
    delete_important_fact,
    _get_scope
)

setting_bp = Blueprint("setting", __name__)


# =========================
# 重點記憶設定表單
# 目前先開放私聊 chat_id；群組 chat_id 先保留延伸，不開放寫入。
# =========================
@setting_bp.route("/setting/important_memory", methods=["GET"])
def important_memory_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")

    if not bot_id or not chat_id:
        return "缺少 bot_id 或 chat_id", 400

    try:
        is_group = int(chat_id) < 0
    except Exception:
        is_group = str(chat_id).startswith("-")

    return render_template(
        "important_memory_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        is_group=is_group
    )


# =========================
# 儲存重點記憶
# =========================
@setting_bp.route("/setting/important_memory/save", methods=["POST"])
def save_important_memory_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    user_id = request.form.get("user_id", "").strip()
    fact = request.form.get("important_memory", "").strip()

    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    try:
        is_group = int(chat_id) < 0
    except Exception:
        is_group = str(chat_id).startswith("-")

    if is_group:
        return jsonify({
            "ok": False,
            "message": "群組重點記憶欄位已預留，但目前暫不開放群組寫入。"
        }), 400

    if not fact:
        return jsonify({
            "ok": False,
            "message": "請輸入要保存的重點記憶。"
        }), 400

    add_important_fact(
        bot_id=bot_id,
        chat_id=chat_id,
        fact=fact,
        scope=_get_scope(chat_id),
        user_id=user_id
    )

    return jsonify({
        "ok": True,
        "message": "重點記憶已儲存。"
    })


# =========================
# 取得重點記憶清單
# =========================
@setting_bp.route("/setting/important_memory/list", methods=["GET"])
def list_important_memory_setting():

    bot_id = request.args.get("bot_id", "").strip()
    chat_id = request.args.get("chat_id", "").strip()
    user_id = request.args.get("user_id", "").strip()

    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    try:
        is_group = int(chat_id) < 0
    except Exception:
        is_group = str(chat_id).startswith("-")

    if is_group:
        return jsonify({
            "ok": False,
            "message": "群組重點記憶欄位已預留，但目前暫不開放群組讀取。"
        }), 400

    memories = list_important_facts(
        bot_id=bot_id,
        chat_id=chat_id,
        scope=_get_scope(chat_id),
        user_id=user_id,
        limit=100
    )

    return jsonify({
        "ok": True,
        "memories": memories
    })


# =========================
# 修改單筆重點記憶
# =========================
@setting_bp.route("/setting/important_memory/update", methods=["POST"])
def update_important_memory_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    user_id = request.form.get("user_id", "").strip()
    memory_id = request.form.get("memory_id", "").strip()
    fact = request.form.get("important_memory", "").strip()

    if not bot_id or not chat_id or not memory_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id、chat_id 或 memory_id"
        }), 400

    if not fact:
        return jsonify({
            "ok": False,
            "message": "重點記憶不能空白。"
        }), 400

    ok, message = update_important_fact(
        memory_id=memory_id,
        bot_id=bot_id,
        chat_id=chat_id,
        fact=fact,
        scope=_get_scope(chat_id),
        user_id=user_id
    )

    status = 200 if ok else 400
    return jsonify({
        "ok": ok,
        "message": message
    }), status


# =========================
# 刪除單筆重點記憶
# =========================
@setting_bp.route("/setting/important_memory/delete", methods=["POST"])
def delete_important_memory_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    user_id = request.form.get("user_id", "").strip()
    memory_id = request.form.get("memory_id", "").strip()

    if not bot_id or not chat_id or not memory_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id、chat_id 或 memory_id"
        }), 400

    ok, message = delete_important_fact(
        memory_id=memory_id,
        bot_id=bot_id,
        chat_id=chat_id,
        scope=_get_scope(chat_id),
        user_id=user_id
    )

    status = 200 if ok else 404
    return jsonify({
        "ok": ok,
        "message": message
    }), status


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


    mode = get_character_mode(bot_id, chat_id, user_id=user_id)

    # =========================
    # 劇場模式 → 原本劇本表單
    # =========================
    if mode == "劇場模式":

        settings = get_character_settings(bot_id, chat_id, user_id=user_id)

        return render_template(
            "character_form.html",
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            settings=settings
        )

    # =========================
    # 聊天模式 → 聊天人物表單
    # =========================
    settings = get_chat_persona_settings(bot_id, chat_id, user_id=user_id)

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


    settings = get_character_settings(bot_id, chat_id, user_id=user_id)

    return render_template(
        "character_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        settings=settings
    )


# =========================
# 回覆風格設定表單
# style_type：chat / theater
# =========================
@setting_bp.route("/setting/reply_style", methods=["GET"])
def reply_style_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")
    style_type = normalize_style_type(request.args.get("style_type", "chat"))

    if not bot_id or not chat_id:
        return "缺少 bot_id 或 chat_id", 400


    settings = get_reply_style_settings(bot_id, chat_id, style_type, user_id=user_id)

    if style_type == "theater":
        title = "劇場回覆風格"
        subtitle = "這裡只控制劇場模式的輸出長相，不會跟劇本綁定。"
        default_style = DEFAULT_THEATER_REPLY_STYLE.strip()
    else:
        title = "聊天回覆風格"
        subtitle = "這裡只控制聊天模式的輸出長相，不會跟聊天對象綁定。"
        default_style = DEFAULT_CHAT_REPLY_STYLE.strip()

    editor_style = (settings.get("reply_style", "") or "").strip() or default_style

    return render_template(
        "reply_style_form.html",
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        style_type=style_type,
        title=title,
        subtitle=subtitle,
        default_style=default_style,
        editor_style=editor_style,
        settings=settings
    )


# =========================
# 儲存回覆風格設定
# 空白代表使用系統預設
# =========================
@setting_bp.route("/setting/reply_style/save", methods=["POST"])
def save_reply_style_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    style_type = normalize_style_type(request.form.get("style_type", "chat"))
    user_id = request.form.get("user_id", "").strip()


    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    reply_style = request.form.get("reply_style", "").strip()

    if not reply_style:
        if style_type == "theater":
            reply_style = DEFAULT_THEATER_REPLY_STYLE.strip()
        else:
            reply_style = DEFAULT_CHAT_REPLY_STYLE.strip()

    update_reply_style_settings(
        bot_id=bot_id,
        chat_id=chat_id,
        style_type=style_type,
        reply_style=reply_style,
        user_id=user_id
    )

    return jsonify({
        "ok": True,
        "message": "回覆風格已儲存，可以關閉此頁。"
    })


# =========================
# 儲存聊天模式人物設定
# 不必填，允許全部空白
# 回覆風格已獨立，不在這裡儲存
# =========================
@setting_bp.route("/setting/chat_persona/save", methods=["POST"])
def save_chat_persona_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    user_id = request.form.get("user_id", "").strip()


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

    update_chat_persona_settings(bot_id, chat_id, settings, user_id=user_id)

    return jsonify({
        "ok": True,
        "message": "聊天人物設定已儲存，可以關閉此頁。"
    })


# =========================
# 儲存劇本設定
# 回覆風格已獨立，不在這裡儲存
# =========================
@setting_bp.route("/setting/character/save", methods=["POST"])
def save_character_setting():

    bot_id = request.form.get("bot_id", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    user_id = request.form.get("user_id", "").strip()


    if not bot_id or not chat_id:
        return jsonify({
            "ok": False,
            "message": "缺少 bot_id 或 chat_id"
        }), 400

    current_settings = get_character_settings(bot_id, chat_id, user_id=user_id)

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
        "story_background": "故事背景"
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

    update_character_settings(bot_id, chat_id, settings, user_id=user_id)

    return jsonify({
        "ok": True,
        "message": "劇本設定已儲存，可以關閉此頁。"
    })
