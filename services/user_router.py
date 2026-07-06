from services.database import get_conn
from services.runtime_cache import get_cache, set_cache, delete_cache


def _text_id(value):
    return str(value)

# =========================
# 取得 Gemini API key
# =========================
def get_gemini_key(user_id: int):
    """
    根據 user_id 從 DB 取得 Gemini API key。

    API key 幾乎不會每句話都改，所以先放 runtime cache。
    後台更新 key 時會呼叫 clear_gemini_key_cache() 主動清除。
    """

    user_id = _text_id(user_id)
    cache_key = ("gemini_key", user_id)

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT gemini_key
        FROM user_config
        WHERE user_id = %s
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        return set_cache(cache_key, row[0], ttl=600)

    return None


def clear_gemini_key_cache(user_id):
    """後台更新 Gemini key 後呼叫，避免繼續拿到舊 key。"""
    delete_cache(("gemini_key", _text_id(user_id)))

# =========================
# 檢查 user 是否有 key
# =========================
def user_has_key(user_id: int) -> bool:

    user_id = _text_id(user_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM user_config
        WHERE user_id = %s
    """, (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result is not None