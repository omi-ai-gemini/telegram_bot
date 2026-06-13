from services.database import get_conn

# =========================
# 取得 bot token
# =========================
def get_bot_token(bot_id: str):
    """
    根據 bot_id 從 DB 取得 Telegram Bot Token
    """

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT token
        FROM bot_config
        WHERE bot_id = ?
    """, (bot_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row["token"]

    return None

# =========================
# 檢查 bot 是否存在
# =========================
def bot_exists(bot_id: str) -> bool:

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM bot_config
        WHERE bot_id = ?
    """, (bot_id,))

    result = cursor.fetchone()
    conn.close()

    return result is not None