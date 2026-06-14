from services.database import get_conn


def _text_id(value):
    return str(value)

# =========================
# 取得 Gemini API key
# =========================
def get_gemini_key(user_id: int):
    """
    根據 user_id 從 DB 取得 Gemini API key
    """

    user_id = _text_id(user_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT gemini_key
        FROM user_config
        WHERE user_id = %s
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]

    return None

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