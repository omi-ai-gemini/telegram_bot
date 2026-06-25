from services.database import get_conn

def get_character_mode(bot_id, chat_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT mode
        FROM character_settings
        WHERE bot_id = %s
          AND chat_id = %s
    """, (
        str(bot_id),
        str(chat_id)
    ))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]

    return "聊天模式"


def update_character_mode(bot_id, chat_id, mode):

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO character_settings (
                bot_id,
                chat_id,
                mode,
                updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                mode = EXCLUDED.mode,
                updated_at = CURRENT_TIMESTAMP
        """, (
            str(bot_id),
            str(chat_id),
            mode
        ))

        conn.commit()

        print("DEBUG character mode updated:", bot_id, chat_id, mode)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_character_mode:", e)
        raise

    finally:
        conn.close()