from services.database import get_conn


DEFAULT_CHAT_PERSONA_SETTINGS = {
    "persona_name": "",
    "persona_gender": "",
    "persona_background": ""
}


def _text_id(value):
    return str(value)


# =========================
# 檢查是否有設定聊天人物
# =========================
def has_chat_persona_settings(settings):

    if not settings:
        return False

    return any([
        settings.get("persona_name", "").strip(),
        settings.get("persona_gender", "").strip(),
        settings.get("persona_background", "").strip()
    ])


# =========================
# 取得聊天模式人物設定
# =========================
def get_chat_persona_settings(bot_id, chat_id):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                persona_name,
                persona_gender,
                persona_background
            FROM chat_persona_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        row = cursor.fetchone()

        if not row:
            return DEFAULT_CHAT_PERSONA_SETTINGS.copy()

        return {
            "persona_name": row[0] or "",
            "persona_gender": row[1] or "",
            "persona_background": row[2] or ""
        }

    except Exception as e:
        print("DB ERROR get_chat_persona_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 更新聊天模式人物設定
# =========================
def update_chat_persona_settings(bot_id, chat_id, settings):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    persona_name = settings.get("persona_name", "")
    persona_gender = settings.get("persona_gender", "")
    persona_background = settings.get("persona_background", "")

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO chat_persona_settings (
                bot_id,
                chat_id,
                persona_name,
                persona_gender,
                persona_background,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                persona_name = EXCLUDED.persona_name,
                persona_gender = EXCLUDED.persona_gender,
                persona_background = EXCLUDED.persona_background,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            persona_name,
            persona_gender,
            persona_background
        ))

        conn.commit()

        print("DEBUG chat persona updated:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_chat_persona_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除聊天模式人物設定
# =========================
def delete_chat_persona_settings(bot_id, chat_id):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM chat_persona_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        conn.commit()

        print("DEBUG chat persona deleted:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_chat_persona_settings:", e)
        raise

    finally:
        conn.close()
