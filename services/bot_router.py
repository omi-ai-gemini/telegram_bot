from services.database import get_conn
from services.crypto_env import decrypt_text, is_encrypted, aad_for



def _decrypt_bot_token_safe(bot_id, value):
    if not is_encrypted(value):
        return value

    try:
        return decrypt_text(value, aad=aad_for("bot_config", "token", bot_id))
    except Exception as exc:
        print("BOT TOKEN DECRYPT ERROR:", exc, flush=True)
        return None

# =========================
# bot token 快取
# =========================
_TOKEN_CACHE = {}

def _text_id(value):
    return str(value)

# =========================
# 取得 bot token
# =========================
def get_bot_token(bot_id: str):
    """
    根據 bot_id 從 DB 取得 Telegram Bot Token
    第一次查 DB，之後同一個 bot_id 直接走記憶體快取
    """

    bot_id = _text_id(bot_id)

    # 先從記憶體快取拿
    if bot_id in _TOKEN_CACHE:
        return _TOKEN_CACHE[bot_id]

    # 快取沒有，才查 DB
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT token
        FROM bot_config
        WHERE bot_id = %s
    """, (bot_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        token = _decrypt_bot_token_safe(bot_id, row[0])
        if token:
            _TOKEN_CACHE[bot_id] = token
        return token

    return None

# =========================
# 檢查 bot 是否存在
# =========================
def bot_exists(bot_id: str) -> bool:

    bot_id = _text_id(bot_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM bot_config
        WHERE bot_id = %s
    """, (bot_id,))

    result = cursor.fetchone()
    conn.close()

    return result is not None

# =========================
# 清除指定 bot token 快取
# =========================
def clear_bot_token_cache(bot_id: str):
    """
    後台更新 bot token 後使用
    避免繼續拿到舊 token
    """

    bot_id = _text_id(bot_id)

    _TOKEN_CACHE.pop(bot_id, None)