import requests

from config import SERVICE_CENTER_BOT_TOKEN, TELEGRAM_API_BASE


_SERVICE_CENTER_SESSION = requests.Session()


def _telegram_post(method, payload, timeout=30):
    """
    服務中心 bot 專用 Telegram API。

    注意：
    - 不查 bot_config。
    - 不走 services.telegram_service。
    - token 只讀 SERVICE_CENTER_BOT_TOKEN 環境變數。
    """
    token = str(SERVICE_CENTER_BOT_TOKEN or "").strip()

    if not token:
        print("SERVICE CENTER TOKEN NOT SET: SERVICE_CENTER_BOT_TOKEN", flush=True)
        return None

    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"

    try:
        res = _SERVICE_CENTER_SESSION.post(url, json=payload, timeout=timeout)
    except Exception as exc:
        print(f"SERVICE CENTER TELEGRAM {method} REQUEST ERROR:", exc, flush=True)
        return None

    if not res.ok:
        print(f"SERVICE CENTER TELEGRAM {method} ERROR:", res.text, flush=True)
        return None

    try:
        return res.json()
    except Exception:
        return {"ok": True}


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": str(text or ""),
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _telegram_post("sendMessage", payload)


def edit_message_text(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": str(text or ""),
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _telegram_post("editMessageText", payload)


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    payload = {
        "callback_query_id": callback_query_id,
    }

    if text:
        payload["text"] = str(text)

    if show_alert:
        payload["show_alert"] = True

    return _telegram_post("answerCallbackQuery", payload, timeout=10)


def delete_message(chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }

    return _telegram_post("deleteMessage", payload, timeout=10)
