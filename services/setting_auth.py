import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Iterable, Optional

from config import SETTING_LINK_SECRET


# =========================
# 設定頁簽章網址鎖
# =========================
# 目的：
# - bot_id / chat_id / user_id 只能當資料索引，不能當權限
# - 設定頁 URL 必須帶有後端簽出的 token
# - token 15 分鐘後失效
# - 群組設定頁目前先保留延伸，不開放
# =========================
SETTING_LINK_TTL_SECONDS = 15 * 60


class SettingAuthError(Exception):
    pass


def _text_id(value: Any) -> str:
    return str(value or "").strip()


def is_group_chat(chat_id: Any) -> bool:
    chat_id = _text_id(chat_id)

    try:
        return int(chat_id) < 0
    except Exception:
        return chat_id.startswith("-")


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("utf-8"))


def _get_secret() -> bytes:
    secret = _text_id(SETTING_LINK_SECRET)

    if not secret:
        raise SettingAuthError("SETTING_LINK_SECRET is not set")

    return secret.encode("utf-8")


def _sign(payload_part: str) -> str:
    digest = hmac.new(
        _get_secret(),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return _b64_encode(digest)


def create_setting_token(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    page_type: str,
    ttl_seconds: int = SETTING_LINK_TTL_SECONDS,
) -> Optional[str]:
    """
    建立設定頁 token。

    回傳 None 代表不能建立網址：
    - 群組聊天室目前不開放設定頁
    - SETTING_LINK_SECRET 未設定
    """
    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    page_type = _text_id(page_type)

    if not user_id or not bot_id or not chat_id or not page_type:
        return None

    if is_group_chat(chat_id):
        return None

    payload = {
        "user_id": user_id,
        "bot_id": bot_id,
        "chat_id": chat_id,
        "page_type": page_type,
        "expires_at": int(time.time()) + int(ttl_seconds),
        "nonce": secrets.token_urlsafe(12),
    }

    try:
        payload_part = _b64_encode(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        signature = _sign(payload_part)
    except Exception as exc:
        print("SETTING TOKEN CREATE ERROR:", exc)
        return None

    return f"{payload_part}.{signature}"


def verify_setting_token(
    token: Any,
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    page_type: Optional[str] = None,
    allowed_page_types: Optional[Iterable[str]] = None,
) -> dict:
    """
    驗證設定頁 token。

    回傳格式：
    {
      ok: bool,
      status: int,
      message: str,
      reason: str,
      payload: dict
    }
    """
    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    token = _text_id(token)

    if not bot_id or not chat_id or not user_id:
        return _fail("missing", "缺少 bot_id、chat_id 或 user_id", 400)

    if is_group_chat(chat_id):
        return _fail("group_disabled", "群組設定頁暫不開放，請私訊 bot 使用 /設定。", 403)

    if not token:
        return _fail("missing_token", "設定連結缺少授權 token，請回 Telegram 重新開啟設定。", 403)

    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        return _fail("bad_token", "設定連結格式錯誤，請回 Telegram 重新開啟設定。", 403)

    try:
        expected_signature = _sign(payload_part)
    except Exception as exc:
        print("SETTING TOKEN VERIFY ERROR:", exc)
        return _fail("secret_missing", "SETTING_LINK_SECRET 尚未設定，無法開啟設定頁。", 500)

    if not hmac.compare_digest(signature, expected_signature):
        return _fail("bad_signature", "設定連結驗證失敗，請回 Telegram 重新開啟設定。", 403)

    try:
        payload = json.loads(_b64_decode(payload_part).decode("utf-8"))
    except Exception:
        return _fail("bad_payload", "設定連結內容錯誤，請回 Telegram 重新開啟設定。", 403)

    if _text_id(payload.get("user_id")) != user_id:
        return _fail("user_mismatch", "設定連結使用者不一致，請回 Telegram 重新開啟設定。", 403)

    if _text_id(payload.get("bot_id")) != bot_id:
        return _fail("bot_mismatch", "設定連結 bot 不一致，請回 Telegram 重新開啟設定。", 403)

    if _text_id(payload.get("chat_id")) != chat_id:
        return _fail("chat_mismatch", "設定連結聊天室不一致，請回 Telegram 重新開啟設定。", 403)

    token_page_type = _text_id(payload.get("page_type"))

    if allowed_page_types is not None:
        allowed = {_text_id(item) for item in allowed_page_types}

        if token_page_type not in allowed:
            return _fail("page_mismatch", "設定連結頁面不一致，請回 Telegram 重新開啟設定。", 403)

    elif page_type is not None and token_page_type != _text_id(page_type):
        return _fail("page_mismatch", "設定連結頁面不一致，請回 Telegram 重新開啟設定。", 403)

    expires_at = int(payload.get("expires_at") or 0)

    if expires_at <= int(time.time()):
        return _fail("expired", "設定連結已失效，請回 Telegram 重新開啟設定。", 403, payload=payload)

    return {
        "ok": True,
        "status": 200,
        "message": "ok",
        "reason": "ok",
        "payload": payload,
        "expires_at": expires_at,
    }


def verify_setting_request(
    flask_request,
    page_type: Optional[str] = None,
    allowed_page_types: Optional[Iterable[str]] = None,
) -> dict:
    values = flask_request.values

    return verify_setting_token(
        token=values.get("token", ""),
        user_id=values.get("user_id", ""),
        bot_id=values.get("bot_id", ""),
        chat_id=values.get("chat_id", ""),
        page_type=page_type,
        allowed_page_types=allowed_page_types,
    )


def _fail(reason: str, message: str, status: int, payload: Optional[dict] = None) -> dict:
    return {
        "ok": False,
        "status": status,
        "message": message,
        "reason": reason,
        "payload": payload or {},
        "expires_at": int((payload or {}).get("expires_at") or 0),
    }
