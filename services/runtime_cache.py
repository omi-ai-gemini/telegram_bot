import copy
import threading
import time

# =========================
# Runtime TTL 快取
# =========================
# 用途：
# - 減少每次 AI 回覆前重複查 DB。
# - 適合放「常讀、不常改」的資料，例如 API key、人物設定、風格、重點記憶。
#
# 注意：
# - 只存在 Render process 記憶體。
# - Render 重啟會清空，這是正常現象。
# - 多 worker 時每個 worker 各自一份快取。
# - 更新設定後要呼叫 delete_cache() / clear_*_cache() 主動清掉。

_CACHE = {}
_LOCK = threading.Lock()


def _now():
    return time.time()


def get_cache(key, default=None):
    """取得快取，過期或不存在就回傳 default。"""
    now = _now()

    with _LOCK:
        item = _CACHE.get(key)

        if not item:
            return default

        expires_at, value = item

        if expires_at <= now:
            _CACHE.pop(key, None)
            return default

        try:
            return copy.deepcopy(value)
        except Exception:
            return value


def set_cache(key, value, ttl=60):
    """寫入快取，ttl 單位為秒。"""
    try:
        cached_value = copy.deepcopy(value)
    except Exception:
        cached_value = value

    with _LOCK:
        _CACHE[key] = (_now() + int(ttl or 60), cached_value)

    return value


def delete_cache(key_or_prefix):
    """
    刪除快取。

    - 傳完整 key：刪除單筆
    - 傳 tuple prefix：刪除所有以前綴開頭的 key
      例如 delete_cache(("character_settings", bot_id, chat_id))
    """
    with _LOCK:
        if isinstance(key_or_prefix, tuple):
            keys = [
                key for key in list(_CACHE.keys())
                if isinstance(key, tuple)
                and key[:len(key_or_prefix)] == key_or_prefix
            ]

            for key in keys:
                _CACHE.pop(key, None)

            return len(keys)

        return 1 if _CACHE.pop(key_or_prefix, None) else 0


def clear_cache():
    """清空全部 runtime cache。"""
    with _LOCK:
        count = len(_CACHE)
        _CACHE.clear()
        return count


def get_cache_stats():
    """除錯用：回傳目前快取數量。"""
    with _LOCK:
        return {"items": len(_CACHE)}
