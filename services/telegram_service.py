import requests
from config import TELEGRAM_API_BASE
from services.bot_router import get_bot_token

# =========================
# Telegram 發送訊息
# =========================
def send_message(bot_id, chat_id, text):

    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return
    
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

    res = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    if not res.ok:
        print("TELEGRAM sendMessage ERROR:", res.text)


# =========================
# Telegram callback 提示
# =========================
def answer_callback_query(bot_id, callback_query_id, text=None, show_alert=False):

    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return

    url = f"{TELEGRAM_API_BASE}/bot{token}/answerCallbackQuery"

    payload = {
        "callback_query_id": callback_query_id
    }

    if text:
        payload["text"] = text

    if show_alert:
        payload["show_alert"] = True

    res = requests.post(
        url,
        json=payload,
        timeout=10
    )

    if not res.ok:
        print("TELEGRAM answerCallbackQuery ERROR:", res.text)


# =========================
# Telegram 刪除訊息
# =========================
def delete_message(bot_id, chat_id, message_id):

    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return

    url = f"{TELEGRAM_API_BASE}/bot{token}/deleteMessage"

    res = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "message_id": message_id
        },
        timeout=10
    )

    if not res.ok:
        print("TELEGRAM deleteMessage ERROR:", res.text)