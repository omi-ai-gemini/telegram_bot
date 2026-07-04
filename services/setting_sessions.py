from services.database import get_conn


def _text_id(value):
    return str(value or "").strip()


def save_setting_menu_session(bot_id, chat_id, user_id, menu_message_id, command_message_id):
    """記錄 /setting 指令訊息與設定選單訊息的對應，方便按退出時一起刪除。"""
    if not menu_message_id or not command_message_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO setting_menu_sessions (
                bot_id,
                chat_id,
                user_id,
                menu_message_id,
                command_message_id,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id, menu_message_id)

            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                command_message_id = EXCLUDED.command_message_id,
                created_at = CURRENT_TIMESTAMP
        """, (
            _text_id(bot_id),
            _text_id(chat_id),
            _text_id(user_id),
            int(menu_message_id),
            int(command_message_id),
        ))

        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("DB ERROR save_setting_menu_session:", exc)
        return False

    finally:
        conn.close()


def pop_setting_menu_session(bot_id, chat_id, menu_message_id, user_id=None):
    """取出並刪除設定選單 session，回傳原始 /setting 訊息 message_id。"""
    if not menu_message_id:
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()

        params = [_text_id(bot_id), _text_id(chat_id), int(menu_message_id)]
        user_sql = ""

        if user_id is not None:
            user_sql = "AND (user_id = %s OR user_id IS NULL OR user_id = '')"
            params.append(_text_id(user_id))

        cursor.execute(f"""
            SELECT id, command_message_id
            FROM setting_menu_sessions
            WHERE bot_id = %s
              AND chat_id = %s
              AND menu_message_id = %s
              {user_sql}
            ORDER BY created_at DESC
            LIMIT 1
        """, params)

        row = cursor.fetchone()

        if not row:
            return None

        session_id, command_message_id = row

        cursor.execute("""
            DELETE FROM setting_menu_sessions
            WHERE id = %s
        """, (session_id,))

        conn.commit()
        return int(command_message_id) if command_message_id else None

    except Exception as exc:
        conn.rollback()
        print("DB ERROR pop_setting_menu_session:", exc)
        return None

    finally:
        conn.close()
