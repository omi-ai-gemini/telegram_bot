import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional


IMAGE_LINK_TTL_SECONDS = 20 * 60


def _text(value: Any) -> str:
    return str(value or "").strip()


def _secret() -> bytes:
    value = (
        os.getenv("SETTING_LINK_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("FLASK_SECRET_KEY")
        or ""
    )
    if not value:
        raise RuntimeError("SETTING_LINK_SECRET is not set")
    return value.encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("utf-8"))


def create_image_token(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    page_type: str,
    action_id: Optional[Any] = None,
    ttl_seconds: int = IMAGE_LINK_TTL_SECONDS,
) -> str:
    payload = {
        "u": _text(user_id),
        "b": _text(bot_id),
        "c": _text(chat_id),
        "p": _text(page_type),
        "a": None if action_id is None else _text(action_id),
        "exp": int(time.time()) + int(ttl_seconds or IMAGE_LINK_TTL_SECONDS),
        "n": secrets.token_urlsafe(8),
    }
    payload_part = _b64e(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret(), payload_part.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64e(signature)}"


def verify_image_token(token: str, expected_page: Optional[str] = None) -> Dict[str, Any]:
    try:
        payload_part, signature_part = _text(token).split(".", 1)
        expected = hmac.new(_secret(), payload_part.encode("utf-8"), hashlib.sha256).digest()
        actual = _b64d(signature_part)
        if not hmac.compare_digest(expected, actual):
            return {"ok": False, "reason": "bad_signature", "message": "連結驗證失敗"}

        payload = json.loads(_b64d(payload_part).decode("utf-8"))
        if int(payload.get("exp") or 0) < int(time.time()):
            return {"ok": False, "reason": "expired", "message": "連結已超過 20 分鐘，請回 Telegram 重新開啟"}

        if expected_page and _text(payload.get("p")) != _text(expected_page):
            return {"ok": False, "reason": "wrong_page", "message": "連結用途不正確"}

        return {
            "ok": True,
            "user_id": _text(payload.get("u")),
            "bot_id": _text(payload.get("b")),
            "chat_id": _text(payload.get("c")),
            "page_type": _text(payload.get("p")),
            "action_id": payload.get("a"),
            "expires_at": int(payload.get("exp") or 0),
        }
    except Exception as exc:
        print("IMAGE TOKEN VERIFY ERROR:", exc, flush=True)
        return {"ok": False, "reason": "bad_format", "message": "連結格式錯誤"}
