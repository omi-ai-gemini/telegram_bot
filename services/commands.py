import requests
from services.bot_router import get_bot_token
from services.character import get_character_mode

def _telegram_post(bot_id, method, payload):

    bot_token = get_bot_token(bot_id)

    if not bot_token:
        print("X token not found")
        return

    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    res = requests.post(url, json=payload, timeout=30)

    if not res.ok:
        print("TELEGRAM ERROR:", res.text)

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

def send_character_menu(bot_id, chat_id, message_id=None, mode=None):

    if mode is None:
        mode = get_character_mode(bot_id, chat_id)

    _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "👤 人物設定",
        [
            [{"text": f"🎭 模式｜{mode}", "callback_data": "character_mode"}],
            [{"text": "📝 角色設定", "callback_data": "edit_role"}],
            [{"text": "👤 個人設定", "callback_data": "edit_user"}],
            [{"text": "💬 角色開場白", "callback_data": "edit_opening"}],
            [{"text": "🗑️ 刪除所有設定", "callback_data": "delete_character"}],
            [{"text": "⬅️ 返回", "callback_data": "back_setting"}]
        ]
    )
    
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
