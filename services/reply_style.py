from services.database import get_conn


# =========================
# 回覆風格設定
# style_type：
# - chat：聊天模式
# - theater：劇場模式
# =========================
DEFAULT_REPLY_STYLE_SETTINGS = {
    "style_type": "chat",
    "reply_style": ""
}


def _text_id(value):
    return str(value)


# =========================
# 正規化風格類型
# 允許 route 傳 chat/theater
# 也允許 AI 流程傳 聊天模式/劇場模式
# =========================
def normalize_style_type(style_type):

    style_type = str(style_type or "").strip()

    if style_type in ["劇場模式", "theater", "劇場", "T"]:
        return "theater"

    return "chat"


# =========================
# 取得舊版風格欄位
# 用於平滑過渡：
# 如果你之前已經把 reply_style 存在 character_settings / chat_persona_settings，
# 新表還沒有資料時，會先讀舊欄位，避免舊資料直接失效。
# 如果舊欄位不存在，會自動略過。
# =========================
def _get_legacy_reply_style(cursor, bot_id, chat_id, style_type):

    try:
        if style_type == "theater":
            cursor.execute("""
                SELECT reply_style
                FROM character_settings
                WHERE bot_id = %s
                  AND chat_id = %s
            """, (
                bot_id,
                chat_id
            ))
        else:
            cursor.execute("""
                SELECT reply_style
                FROM chat_persona_settings
                WHERE bot_id = %s
                  AND chat_id = %s
            """, (
                bot_id,
                chat_id
            ))

        row = cursor.fetchone()

        if row and row[0]:
            return row[0]

    except Exception as e:
        # 舊欄位不存在時會進來，這是正常過渡狀況
        print("DEBUG legacy reply_style not available:", e)

    return ""


# =========================
# 取得回覆風格設定
# =========================
def get_reply_style_settings(bot_id, chat_id, style_type):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    style_type = normalize_style_type(style_type)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT reply_style
            FROM reply_style_settings
            WHERE bot_id = %s
              AND chat_id = %s
              AND style_type = %s
        """, (
            bot_id,
            chat_id,
            style_type
        ))

        row = cursor.fetchone()

        if row:
            return {
                "style_type": style_type,
                "reply_style": row[0] or ""
            }

        # =========================
        # 新表沒有資料時，嘗試讀舊欄位
        # 如果讀到舊版風格，順手搬到新表，避免之後換人物 / 換劇本時遺失
        # =========================
        legacy_reply_style = _get_legacy_reply_style(
            cursor,
            bot_id,
            chat_id,
            style_type
        )

        if legacy_reply_style:
            cursor.execute("""
                INSERT INTO reply_style_settings (
                    bot_id,
                    chat_id,
                    style_type,
                    reply_style,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)

                ON CONFLICT (bot_id, chat_id, style_type)

                DO UPDATE SET
                    reply_style = EXCLUDED.reply_style,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                bot_id,
                chat_id,
                style_type,
                legacy_reply_style
            ))

            conn.commit()

            print("DEBUG legacy reply style migrated:", bot_id, chat_id, style_type)

        return {
            "style_type": style_type,
            "reply_style": legacy_reply_style or ""
        }

    except Exception as e:
        print("DB ERROR get_reply_style_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 更新回覆風格設定
# 空白也允許，空白代表使用系統預設樣式
# =========================
def update_reply_style_settings(bot_id, chat_id, style_type, reply_style):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    style_type = normalize_style_type(style_type)
    reply_style = str(reply_style or "")

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reply_style_settings (
                bot_id,
                chat_id,
                style_type,
                reply_style,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, CURRENT_TIMESTAMP
            )

            ON CONFLICT (bot_id, chat_id, style_type)

            DO UPDATE SET
                reply_style = EXCLUDED.reply_style,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            style_type,
            reply_style
        ))

        conn.commit()

        print("DEBUG reply style updated:", bot_id, chat_id, style_type)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_reply_style_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除回覆風格設定
# style_type=None → 刪聊天 + 劇場
# style_type=chat/theater → 只刪指定模式
# =========================
def delete_reply_style_settings(bot_id, chat_id, style_type=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        if style_type:
            style_type = normalize_style_type(style_type)

            cursor.execute("""
                DELETE FROM reply_style_settings
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND style_type = %s
            """, (
                bot_id,
                chat_id,
                style_type
            ))

        else:
            cursor.execute("""
                DELETE FROM reply_style_settings
                WHERE bot_id = %s
                  AND chat_id = %s
            """, (
                bot_id,
                chat_id
            ))

        conn.commit()

        print("DEBUG reply style deleted:", bot_id, chat_id, style_type)

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_reply_style_settings:", e)
        raise

    finally:
        conn.close()
