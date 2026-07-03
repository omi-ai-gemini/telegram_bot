import threading
import time
from typing import Any, Optional, Tuple

# =========================
# 使用者資料庫密碼臨時解鎖狀態
# =========================
# 注意：
# - 不寫 DB
# - Render 重啟會消失
# - 使用者可用 /解鎖 <資料庫密碼> 重新放入記憶體

_UNLOCK_CACHE = {}
_UNLOCK_LOCK = threading.Lock()
_REQUEST_CONTEXT = threading.local()

# 12 小時，避免長期常駐在記憶體
DEFAULT_UNLOCK_TTL_SECONDS = 60 * 60 * 12


def _text_id(value: Any) -> str:
    return str(value)


def _key(user_id: Any, bot_id: Any) -> Tuple[str, str]:
    return (_text_id(user_id), _text_id(bot_id))


def set_request_context(user_id: Any = None, bot_id: Any = None, chat_id: Any = None) -> None:
    _REQUEST_CONTEXT.user_id = None if user_id is None else _text_id(user_id)
    _REQUEST_CONTEXT.bot_id = None if bot_id is None else _text_id(bot_id)
    _REQUEST_CONTEXT.chat_id = None if chat_id is None else _text_id(chat_id)


def get_current_user_id() -> Optional[str]:
    return getattr(_REQUEST_CONTEXT, "user_id", None)


def get_current_bot_id() -> Optional[str]:
    return getattr(_REQUEST_CONTEXT, "bot_id", None)


def get_current_chat_id() -> Optional[str]:
    return getattr(_REQUEST_CONTEXT, "chat_id", None)


def set_unlock_code(user_id: Any, bot_id: Any, unlock_code: str, ttl_seconds: int = DEFAULT_UNLOCK_TTL_SECONDS) -> None:
    if not user_id or not bot_id or not unlock_code:
        return

    expires_at = time.time() + ttl_seconds

    with _UNLOCK_LOCK:
        _UNLOCK_CACHE[_key(user_id, bot_id)] = {
            "unlock_code": str(unlock_code),
            "expires_at": expires_at,
        }


def get_unlock_code(user_id: Any = None, bot_id: Any = None) -> Optional[str]:
    user_id = _text_id(user_id) if user_id is not None else get_current_user_id()
    bot_id = _text_id(bot_id) if bot_id is not None else get_current_bot_id()

    if not user_id or not bot_id:
        return None

    key = _key(user_id, bot_id)
    now = time.time()

    with _UNLOCK_LOCK:
        item = _UNLOCK_CACHE.get(key)

        if not item:
            return None

        if item.get("expires_at", 0) <= now:
            _UNLOCK_CACHE.pop(key, None)
            return None

        return item.get("unlock_code")


def clear_unlock_code(user_id: Any = None, bot_id: Any = None) -> None:
    user_id = _text_id(user_id) if user_id is not None else get_current_user_id()
    bot_id = _text_id(bot_id) if bot_id is not None else get_current_bot_id()

    if not user_id or not bot_id:
        return

    with _UNLOCK_LOCK:
        _UNLOCK_CACHE.pop(_key(user_id, bot_id), None)


def is_unlocked(user_id: Any = None, bot_id: Any = None) -> bool:
    return bool(get_unlock_code(user_id, bot_id))
