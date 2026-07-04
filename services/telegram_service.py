import requests
from config import TELEGRAM_API_BASE
from services.bot_router import get_bot_token


# =========================
# Telegram 共用 POST
# =========================
def _telegram_post(bot_id, method, payload, timeout=30):
    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return None

    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"

    try:
        res = requests.post(url, json=payload, timeout=timeout)
    except Exception as e:
        print(f"TELEGRAM {method} REQUEST ERROR:", e)
        return None

    if not res.ok:
        print(f"TELEGRAM {method} ERROR:", res.text)
        return None

    try:
        return res.json()
    except Exception:
        return {"ok": True}


# =========================
# Telegram 發送訊息
# - reply_markup 可傳 InlineKeyboardMarkup dict
# - 回傳 Telegram JSON，舊流程用 bool 判斷也仍相容
# =========================
def send_message(bot_id, chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _telegram_post(bot_id, "sendMessage", payload, timeout=30)


# =========================
# Telegram 編輯既有訊息文字
# =========================
def edit_message_text(bot_id, chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _telegram_post(bot_id, "editMessageText", payload, timeout=30)


# =========================
# Telegram callback 提示
# =========================
def answer_callback_query(bot_id, callback_query_id, text=None, show_alert=False):
    payload = {
        "callback_query_id": callback_query_id
    }

    if text:
        payload["text"] = text

    if show_alert:
        payload["show_alert"] = True

    return _telegram_post(bot_id, "answerCallbackQuery", payload, timeout=10)


# =========================
# Telegram 刪除訊息
# =========================
def delete_message(bot_id, chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }

    result = _telegram_post(bot_id, "deleteMessage", payload, timeout=10)
    return bool(result)
