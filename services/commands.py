import os
import requests
from urllib.parse import urlencode
from services.bot_router import get_bot_token
from services.character import get_character_mode, get_script_opening_status
from services.setting_auth import create_setting_token, is_group_chat
from services.setting_sessions import save_setting_menu_session

# =========================
# Telegram API POST
# =========================
def _telegram_post(bot_id, method, payload):

    bot_token = get_bot_token(bot_id)

    if not bot_token:
        print("X token not found")
        return None

    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    res = requests.post(url, json=payload, timeout=30)

    if not res.ok:
        print("TELEGRAM ERROR:", res.text)
        return None

    try:
        return res.json()
    except Exception:
        return None


# =========================
# 建立人物 / 劇本設定網址
# 由後端 route 自動依 mode 分流
# =========================
def _build_persona_setting_url(bot_id, chat_id, user_id):

    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url:
        print("X BASE_URL not found")
        return None

    if is_group_chat(chat_id):
        return None

    token = create_setting_token(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        page_type="persona"
    )

    if not token:
        print("X setting token not created for persona")
        return None

    query = urlencode({
        "bot_id": str(bot_id),
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "token": token
    })

    return f"{base_url}/setting/persona?{query}"


# =========================
# 建立回覆風格設定網址
# style_type：chat / theater
# =========================
def _build_important_memory_url(bot_id, chat_id, user_id):

    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url:
        print("X BASE_URL not found")
        return None

    if is_group_chat(chat_id):
        return None

    token = create_setting_token(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        page_type="important_memory"
    )

    if not token:
        print("X setting token not created for important memory")
        return None

    query = urlencode({
        "bot_id": str(bot_id),
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "token": token
    })

    return f"{base_url}/setting/important_memory?{query}"


def _build_reply_style_url(bot_id, chat_id, user_id, style_type):

    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url:
        print("X BASE_URL not found")
        return None

    if is_group_chat(chat_id):
        return None

    style_type = str(style_type)
    token = create_setting_token(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        page_type=f"reply_style:{style_type}"
    )

    if not token:
        print("X setting token not created for reply style")
        return None

    query = urlencode({
        "bot_id": str(bot_id),
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "style_type": style_type,
        "token": token
    })

    return f"{base_url}/setting/reply_style?{query}"


# =========================
# 發送或編輯同一則訊息
# =========================
def _send_or_edit(bot_id, chat_id, message_id, text, inline_keyboard):

    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": inline_keyboard
        }
    }

    if message_id:
        payload["message_id"] = message_id
        return _telegram_post(bot_id, "editMessageText", payload)

    return _telegram_post(bot_id, "sendMessage", payload)


# =========================
# 只發送新訊息
# 用於確認清除 / 確認刪除
# =========================
def _send_new_message(bot_id, chat_id, text, inline_keyboard):

    return _send_or_edit(
        bot_id,
        chat_id,
        None,
        text,
        inline_keyboard
    )


def _extract_message_id(result):
    if not isinstance(result, dict):
        return None

    message = result.get("result") or {}
    return message.get("message_id")


# =========================
# /setting
# =========================
def send_setting_menu(
    bot_id,
    chat_id,
    message_id=None,
    user_id=None,
    source_message_id=None
):

    opening_status = get_script_opening_status(bot_id, chat_id)
    start_script_text = opening_status.get("button_text", "▶️ 開始劇本 | 無開場白")

    result = _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "⚙️ 設定中心",
        [
            [{"text": "👤 人物設定", "callback_data": "character_setting"}],
            [{"text": "🎨 回覆風格", "callback_data": "reply_style_setting"}],
            [{"text": "🧠 記憶設定", "callback_data": "memory_setting"}],
            [{"text": start_script_text, "callback_data": "start_script"}],
            [{"text": "❌ 結束設定", "callback_data": "close_setting_menu"}]
        ]
    )

    # 只有使用者主動輸入 /setting 或 /設定 開新選單時才記錄。
    # 後續 callback 只是 edit 同一則選單，不需要重複寫。
    if source_message_id and not message_id:
        menu_message_id = _extract_message_id(result)

        if menu_message_id:
            save_setting_menu_session(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                menu_message_id=menu_message_id,
                command_message_id=source_message_id
            )

    return result


# =========================
# /setting/人物設定
# =========================
def send_character_menu(bot_id, chat_id, message_id=None, mode=None, user_id=None):

    if mode is None:
        mode = get_character_mode(bot_id, chat_id)

    if mode == "劇場模式":
        setting_text = "📖 劇本設定"
    else:
        setting_text = "💬 聊天對象"

    setting_button = [{"text": setting_text, "callback_data": "script_setting"}]

    if user_id is not None:
        setting_url = _build_persona_setting_url(bot_id, chat_id, user_id)

        if setting_url:
            setting_button = [{"text": setting_text, "url": setting_url}]

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "👤 人物設定",
        [
            [{"text": f"🎭 模式｜{mode}", "callback_data": "character_mode"}],
            setting_button,
            [{"text": "🗑️ 刪除所有設定", "callback_data": "delete_character"}],
            [{"text": "⬅️ 返回", "callback_data": "back_setting"}]
        ]
    )


# =========================
# /setting/回覆風格
# =========================
def send_reply_style_menu(bot_id, chat_id, message_id=None, user_id=None):

    chat_button = [{"text": "自訂風格 | 聊天", "callback_data": "reply_style_chat"}]
    theater_button = [{"text": "自訂風格 | 劇場", "callback_data": "reply_style_theater"}]

    if user_id is not None:
        chat_url = _build_reply_style_url(bot_id, chat_id, user_id, "chat")
        theater_url = _build_reply_style_url(bot_id, chat_id, user_id, "theater")

        if chat_url:
            chat_button = [{"text": "自訂風格 | 聊天", "url": chat_url}]

        if theater_url:
            theater_button = [{"text": "自訂風格 | 劇場", "url": theater_url}]

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "🎨 回覆風格",
        [
            chat_button,
            theater_button,
            [{"text": "🗑️ 刪除自訂風格", "callback_data": "delete_reply_style"}],
            [{"text": "⬅️ 返回", "callback_data": "back_setting"}]
        ]
    )


# =========================
# /setting/開始劇本/再次發送確認
# =========================
def send_start_script_confirm_menu(bot_id, chat_id, message_id=None):

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "⚠️ 此劇本已經開場過。\n\n確定再次發送開場白？",
        [
            [{"text": "✅ 確定再次發送開場白", "callback_data": "confirm_restart_script"}],
            [{"text": "⬅️ 回上一頁", "callback_data": "back_setting"}]
        ]
    )


# =========================
# /setting/人物設定/模式
# =========================
def send_mode_menu(bot_id, chat_id, message_id=None):

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "🎭 選擇模式",
        [
            [{"text": "聊天模式", "callback_data": "mode_chat"}],
            [{"text": "劇場模式", "callback_data": "mode_theater"}],
            [{"text": "⬅️ 返回人物設定", "callback_data": "back_character"}]
        ]
    )


# =========================
# /setting/記憶設定
# =========================
def send_memory_menu(bot_id, chat_id, message_id=None, user_id=None):

    important_button = [{"text": "⭐ 重點記憶", "callback_data": "important_memory_setting"}]

    if user_id is not None:
        important_url = _build_important_memory_url(bot_id, chat_id, user_id)

        if important_url:
            important_button = [{"text": "⭐ 重點記憶", "url": important_url}]

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "🧠 記憶設定",
        [
            important_button,
            [{"text": "🧹 清除當前記憶", "callback_data": "clear_current_memory"}],
            [{"text": "⬅️ 返回設定中心", "callback_data": "back_setting"}]
        ]
    )


# =========================
# 新增確認訊息：清除當前記憶
# =========================
def send_clear_memory_confirm_message(bot_id, chat_id):

    _send_new_message(
        bot_id,
        chat_id,
        "⚠️ 確認清除所有記憶？\n\n會清除：\n- 短期聊天記憶\n- 長期記憶\n- 情緒狀態\n\n不會清除：\n- 聊天對象\n- 劇本設定\n- 回覆風格\n- bot token\n- Gemini API key",
        [
            [{"text": "✅ 確認清除", "callback_data": "confirm_clear_current_memory"}],
            [{"text": "取消清除", "callback_data": "cancel_clear_current_memory"}]
        ]
    )


# =========================
# 新增確認訊息：刪除所有人物 / 劇本設定
# 注意：不刪回覆風格，讓風格可以傳承
# =========================
def send_delete_character_confirm_message(bot_id, chat_id):

    _send_new_message(
        bot_id,
        chat_id,
        "⚠️ 確認刪除人物 / 劇本設定？\n\n會刪除：\n- 聊天對象\n- 劇本設定\n- 短期記憶\n- 長期記憶\n- 情緒狀態\n\n不會刪除：\n- 回覆風格\n- bot token\n- Gemini API key",
        [
            [{"text": "✅ 確認刪除", "callback_data": "confirm_delete_character"}],
            [{"text": "取消刪除", "callback_data": "cancel_delete_character"}]
        ]
    )


# =========================
# 新增確認訊息：刪除回覆風格
# =========================
def send_delete_reply_style_confirm_message(bot_id, chat_id):

    _send_new_message(
        bot_id,
        chat_id,
        "⚠️ 確認刪除自訂回覆風格？\n\n會刪除：\n- 自訂風格 | 聊天\n- 自訂風格 | 劇場\n\n不會刪除：\n- 聊天對象\n- 劇本設定\n- 記憶",
        [
            [{"text": "✅ 確認刪除", "callback_data": "confirm_delete_reply_style"}],
            [{"text": "取消刪除", "callback_data": "cancel_delete_reply_style"}]
        ]
    )
