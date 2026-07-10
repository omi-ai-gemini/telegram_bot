import json
import requests
from config import TELEGRAM_API_BASE
from services.bot_router import get_bot_token


_TELEGRAM_SESSION = requests.Session()


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
        res = _TELEGRAM_SESSION.post(url, json=payload, timeout=timeout)
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
# Telegram 傳送圖片 bytes
# - 成功回傳 Telegram JSON
# - 不附 caption，符合生圖完成後只傳圖片的需求
# =========================
def send_photo_bytes(bot_id, chat_id, image_bytes, filename="image.png", mime_type="image/png", reply_markup=None):
    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return None

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"
    data = {"chat_id": str(chat_id)}

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    files = {
        "photo": (str(filename or "image.png"), image_bytes, str(mime_type or "image/png")),
    }

    try:
        res = _TELEGRAM_SESSION.post(url, data=data, files=files, timeout=120)
    except Exception as exc:
        print("TELEGRAM sendPhoto REQUEST ERROR:", exc, flush=True)
        return None

    if not res.ok:
        print("TELEGRAM sendPhoto ERROR:", res.text[:1000], flush=True)
        return None

    try:
        return res.json()
    except Exception:
        return {"ok": True}


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
def answer_callback_query(bot_id, callback_query_id, text=None, show_alert=False, url=None):
    payload = {
        "callback_query_id": callback_query_id
    }

    if text:
        payload["text"] = text

    if show_alert:
        payload["show_alert"] = True

    if url:
        payload["url"] = url

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


# =========================
# Telegram 取得檔案資訊
# - 給照片 / 貼圖 / 後續語音影片使用
# =========================
def get_file(bot_id, file_id):
    payload = {
        "file_id": file_id,
    }

    return _telegram_post(bot_id, "getFile", payload, timeout=20)


def _extract_file_path(file_result):
    if not isinstance(file_result, dict):
        return None

    result = file_result.get("result") or {}
    return result.get("file_path")


def download_file_bytes(bot_id, file_id, timeout=60):
    """
    下載 Telegram 檔案為 bytes。

    注意：
    - 不長期保存檔案，不佔 Render 磁碟。
    - 失敗時回傳 None。
    """
    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return None

    file_info = get_file(bot_id, file_id)
    file_path = _extract_file_path(file_info)

    if not file_path:
        print("TELEGRAM getFile missing file_path", flush=True)
        return None

    url = f"{TELEGRAM_API_BASE}/file/bot{token}/{file_path}"

    try:
        res = _TELEGRAM_SESSION.get(url, timeout=timeout)
    except Exception as exc:
        print("TELEGRAM downloadFile REQUEST ERROR:", exc, flush=True)
        return None

    if not res.ok:
        print("TELEGRAM downloadFile ERROR:", res.text[:500], flush=True)
        return None

    return {
        "bytes": res.content,
        "file_path": file_path,
        "mime_type": guess_mime_type_from_file_path(file_path),
    }


def guess_mime_type_from_file_path(file_path):
    path = str(file_path or "").lower()

    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return "image/jpeg"

    if path.endswith(".png"):
        return "image/png"

    if path.endswith(".webp"):
        return "image/webp"

    if path.endswith(".gif"):
        return "image/gif"

    if path.endswith(".webm"):
        return "video/webm"

    if path.endswith(".mp4"):
        return "video/mp4"

    return "application/octet-stream"
