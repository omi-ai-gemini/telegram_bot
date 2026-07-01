import os
import requests
from urllib.parse import urlencode
from services.bot_router import get_bot_token
from services.character import get_character_mode

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

    query = urlencode({
        "bot_id": str(bot_id),
        "chat_id": str(chat_id),
        "user_id": str(user_id)
    })

    return f"{base_url}/setting/persona?{query}"


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


# =========================
# /setting
# =========================
def send_setting_menu(bot_id, chat_id, message_id=None):

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "⚙️ 設定中心",
        [
            [{"text": "👤 人物設定", "callback_data": "character_setting"}],
            [{"text": "🧠 記憶設定", "callback_data": "memory_setting"}],
            [{"text": "🔑 API設定", "callback_data": "api_setting"}]
        ]
    )


# =========================
# /setting/人物設定
# =========================
def send_character_menu(bot_id, chat_id, message_id=None, mode=None, user_id=None):

    if mode is None:
        mode = get_character_mode(bot_id, chat_id)

    setting_button = [{"text": "📖 劇本設定", "callback_data": "script_setting"}]

    if user_id is not None:
        setting_url = _build_persona_setting_url(bot_id, chat_id, user_id)

        if setting_url:
            setting_button = [{"text": "📖 劇本設定", "url": setting_url}]

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
def send_memory_menu(bot_id, chat_id, message_id=None):

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "🧠 記憶設定",
        [
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
        "⚠️ 確認清除所有記憶？\n\n會清除：\n- 短期聊天記憶\n- 長期記憶\n- 情緒狀態\n\n不會清除：\n- 劇本設定\n- bot token\n- Gemini API key",
        [
            [{"text": "✅ 確認清除", "callback_data": "confirm_clear_current_memory"}],
            [{"text": "取消清除", "callback_data": "cancel_clear_current_memory"}]
        ]
    )


# =========================
# 新增確認訊息：刪除所有設定
# =========================
def send_delete_character_confirm_message(bot_id, chat_id):

    _send_new_message(
        bot_id,
        chat_id,
        "⚠️ 確認刪除所有記憶？",
        [
            [{"text": "✅ 確認刪除", "callback_data": "confirm_delete_character"}],
            [{"text": "取消刪除", "callback_data": "cancel_delete_character"}]
        ]
    )
