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
        return

    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    res = requests.post(url, json=payload, timeout=30)

    if not res.ok:
        print("TELEGRAM ERROR:", res.text)


# =========================
# 建立劇本設定網址
# =========================
def _build_character_setting_url(bot_id, chat_id, user_id):

    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url:
        print("X BASE_URL not found")
        return None

    query = urlencode({
        "bot_id": str(bot_id),
        "chat_id": str(chat_id),
        "user_id": str(user_id)
    })

    return f"{base_url}/setting/character?{query}"


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
        _telegram_post(bot_id, "editMessageText", payload)
    else:
        _telegram_post(bot_id, "sendMessage", payload)


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

    # 預設 fallback：如果沒有 user_id 或 BASE_URL，先保留 callback，不讓按鈕消失
    script_button = [{"text": "📖 劇本設定", "callback_data": "script_setting"}]

    # 有 user_id 時，改成直接開啟 Render 表單頁
    if user_id is not None:
        script_url = _build_character_setting_url(bot_id, chat_id, user_id)

        if script_url:
            script_button = [{"text": "📖 劇本設定", "url": script_url}]

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "👤 人物設定",
        [
            [{"text": f"🎭 模式｜{mode}", "callback_data": "character_mode"}],
            script_button,
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