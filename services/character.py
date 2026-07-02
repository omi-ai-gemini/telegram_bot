from services.database import get_conn


# =========================
# 預設劇本設定
# 回覆風格已移到 reply_style_settings，不再跟劇本綁定
# =========================
DEFAULT_CHARACTER_SETTINGS = {
    "mode": "聊天模式",

    "ai_name": "",
    "ai_gender": "",
    "ai_appearance": "",
    "story_background": "",
    "ai_opening": "",

    "user_gender": "",
    "user_appearance": "",
    "user_other_settings": ""
}


def _text_id(value):
    return str(value)


# =========================
# 取得人物模式
# =========================
def get_character_mode(bot_id, chat_id):

    settings = get_character_settings(bot_id, chat_id)

    return settings.get("mode") or "聊天模式"


# =========================
# 更新人物模式
# =========================
def update_character_mode(bot_id, chat_id, mode):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

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
            bot_id,
            chat_id,
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


# =========================
# 取得完整劇本設定
# =========================
def get_character_settings(bot_id, chat_id):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                mode,
                ai_name,
                ai_gender,
                ai_appearance,
                story_background,
                ai_opening,
                user_gender,
                user_appearance,
                user_other_settings
            FROM character_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        row = cursor.fetchone()

        if not row:
            return DEFAULT_CHARACTER_SETTINGS.copy()

        return {
            "mode": row[0] or "聊天模式",

            "ai_name": row[1] or "",
            "ai_gender": row[2] or "",
            "ai_appearance": row[3] or "",
            "story_background": row[4] or "",
            "ai_opening": row[5] or "",

            "user_gender": row[6] or "",
            "user_appearance": row[7] or "",
            "user_other_settings": row[8] or ""
        }

    except Exception as e:
        print("DB ERROR get_character_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 更新完整劇本設定
# 不更新 reply_style，避免換劇本時覆蓋獨立風格設定
# =========================
def update_character_settings(bot_id, chat_id, settings):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    mode = settings.get("mode", "聊天模式")

    ai_name = settings.get("ai_name", "")
    ai_gender = settings.get("ai_gender", "")
    ai_appearance = settings.get("ai_appearance", "")
    story_background = settings.get("story_background", "")
    ai_opening = settings.get("ai_opening", "")

    user_gender = settings.get("user_gender", "")
    user_appearance = settings.get("user_appearance", "")
    user_other_settings = settings.get("user_other_settings", "")

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO character_settings (
                bot_id,
                chat_id,
                mode,

                ai_name,
                ai_gender,
                ai_appearance,
                story_background,
                ai_opening,

                user_gender,
                user_appearance,
                user_other_settings,

                updated_at
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                CURRENT_TIMESTAMP
            )

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                mode = EXCLUDED.mode,

                ai_name = EXCLUDED.ai_name,
                ai_gender = EXCLUDED.ai_gender,
                ai_appearance = EXCLUDED.ai_appearance,
                story_background = EXCLUDED.story_background,
                ai_opening = EXCLUDED.ai_opening,

                user_gender = EXCLUDED.user_gender,
                user_appearance = EXCLUDED.user_appearance,
                user_other_settings = EXCLUDED.user_other_settings,

                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            mode,

            ai_name,
            ai_gender,
            ai_appearance,
            story_background,
            ai_opening,

            user_gender,
            user_appearance,
            user_other_settings
        ))

        conn.commit()

        print("DEBUG character settings updated:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_character_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除劇本設定
# 不刪 reply_style_settings，讓劇場風格可以傳承
# =========================
def delete_character_settings(bot_id, chat_id):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM character_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        conn.commit()

        print("DEBUG character settings deleted:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_character_settings:", e)
        raise

    finally:
        conn.close()
