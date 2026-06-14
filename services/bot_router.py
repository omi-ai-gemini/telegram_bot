from services.database import get_conn


def _text_id(value):
    return str(value)

# =========================
# 取得 bot token
# =========================
def get_bot_token(bot_id: str):
    """
    根據 bot_id 從 DB 取得 Telegram Bot Token
    """

    bot_id = _text_id(bot_id)

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
        return row[0]

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