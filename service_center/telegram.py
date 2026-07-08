import os
import time
import requests

from config import SERVICE_CENTER_BOT_ID, SERVICE_CENTER_BOT_TOKEN, TELEGRAM_API_BASE


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

# =========================
# 服務中心 Bot 自動接 webhook
# =========================
# 目的：
# - 只要 Render 環境變數放 SERVICE_CENTER_BOT_TOKEN / SERVICE_CENTER_BOT_ID / BASE_URL
# - 程式啟動後第一次 request 會自動呼叫 Telegram setWebhook
# - 不需要手動 PowerShell
# - 不建 table，不進 bot_config
_SETUP_DONE = False
_NEXT_RETRY_AT = 0
_SETUP_RETRY_SECONDS = 300


def _service_center_token():
    return str(SERVICE_CENTER_BOT_TOKEN or "").strip()


def get_service_center_webhook_url():
    base_url = str(os.getenv("BASE_URL") or "").strip().rstrip("/")
    bot_id = str(SERVICE_CENTER_BOT_ID or "service_center").strip() or "service_center"

    if not base_url:
        return ""

    return f"{base_url}/webhook/{bot_id}"


def setup_service_center_webhook(force=False):
    """
    自動設定服務中心 bot webhook。

    回傳 True 代表已成功或先前已成功。
    回傳 False 代表缺環境變數或 Telegram API 設定失敗。
    """
    global _SETUP_DONE
    global _NEXT_RETRY_AT

    now = time.time()

    if _SETUP_DONE and not force:
        return True

    if not force and _NEXT_RETRY_AT and now < _NEXT_RETRY_AT:
        return False

    token = _service_center_token()
    webhook_url = get_service_center_webhook_url()

    if not token:
        print(
            "SERVICE CENTER WEBHOOK SKIP: SERVICE_CENTER_BOT_TOKEN not set",
            flush=True,
        )
        _NEXT_RETRY_AT = now + _SETUP_RETRY_SECONDS
        return False

    if not webhook_url:
        print(
            "SERVICE CENTER WEBHOOK SKIP: BASE_URL not set",
            flush=True,
        )
        _NEXT_RETRY_AT = now + _SETUP_RETRY_SECONDS
        return False

    api_url = f"{TELEGRAM_API_BASE}/bot{token}/setWebhook"
    payload = {
        "url": webhook_url,
        "drop_pending_updates": False,
    }

    print(
        f"SERVICE CENTER WEBHOOK SET START url={webhook_url}",
        flush=True,
    )

    try:
        res = _SERVICE_CENTER_SESSION.post(api_url, json=payload, timeout=15)
    except Exception as exc:
        print("SERVICE CENTER WEBHOOK SET REQUEST ERROR:", exc, flush=True)
        _NEXT_RETRY_AT = now + _SETUP_RETRY_SECONDS
        return False

    if not res.ok:
        print("SERVICE CENTER WEBHOOK SET ERROR:", res.text, flush=True)
        _NEXT_RETRY_AT = now + _SETUP_RETRY_SECONDS
        return False

    try:
        data = res.json()
    except Exception:
        data = {"ok": True, "raw": res.text}

    if not data.get("ok"):
        print("SERVICE CENTER WEBHOOK SET FAILED:", data, flush=True)
        _NEXT_RETRY_AT = now + _SETUP_RETRY_SECONDS
        return False

    _SETUP_DONE = True
    _NEXT_RETRY_AT = 0

    print(
        f"SERVICE CENTER WEBHOOK SET OK url={webhook_url}",
        flush=True,
    )
    return True


def get_service_center_webhook_info():
    """除錯用：查 Telegram 目前設定的 webhook。"""
    token = _service_center_token()

    if not token:
        return None

    api_url = f"{TELEGRAM_API_BASE}/bot{token}/getWebhookInfo"

    try:
        res = _SERVICE_CENTER_SESSION.get(api_url, timeout=15)
    except Exception as exc:
        print("SERVICE CENTER WEBHOOK INFO REQUEST ERROR:", exc, flush=True)
        return None

    try:
        return res.json()
    except Exception:
        return None

