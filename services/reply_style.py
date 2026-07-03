from services.database import get_conn
from services.encrypted_store import delete_encrypted_payload, get_encrypted_payload, save_encrypted_payload
from services.privacy_session import get_current_user_id, get_unlock_code


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


def _resolve_user_id(user_id=None):
    return _text_id(user_id) if user_id is not None else get_current_user_id()


def _get_code(user_id, bot_id):
    return get_unlock_code(user_id, bot_id)


# =========================
# 正規化風格類型
# =========================
def normalize_style_type(style_type):

    style_type = str(style_type or "").strip()

    if style_type in ["劇場模式", "theater", "劇場", "T"]:
        return "theater"

    return "chat"


# =========================
# 取得舊版風格欄位
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
        print("DEBUG legacy reply_style not available:", e)

    return ""


# =========================
# 取得回覆風格設定（優先讀加密）
# =========================
def get_reply_style_settings(bot_id, chat_id, style_type, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    style_type = normalize_style_type(style_type)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_code(user_id, bot_id)

    if user_id and unlock_code:
        try:
            payload = get_encrypted_payload(
                user_id=user_id,
                bot_id=bot_id,
                chat_id=chat_id,
                data_type="reply_style_settings",
                unlock_code=unlock_code,
                record_key=style_type,
            )

            if payload:
                return {
                    "style_type": style_type,
                    "reply_style": payload.get("reply_style", "") or ""
                }

        except Exception as e:
            print("DECRYPT ERROR get_reply_style_settings:", e)

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

        legacy_reply_style = _get_legacy_reply_style(
            cursor,
            bot_id,
            chat_id,
            style_type
        )

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
# 更新回覆風格設定（加密寫入）
# =========================
def update_reply_style_settings(bot_id, chat_id, style_type, reply_style, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    style_type = normalize_style_type(style_type)
    reply_style = str(reply_style or "")
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_code(user_id, bot_id)

    if not user_id or not unlock_code:
        raise ValueError("尚未解鎖資料庫密碼，無法儲存回覆風格")

    save_encrypted_payload(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        data_type="reply_style_settings",
        unlock_code=unlock_code,
        payload={
            "style_type": style_type,
            "reply_style": reply_style,
        },
        record_key=style_type,
    )

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
            VALUES (%s, %s, %s, '', CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id, style_type)

            DO UPDATE SET
                reply_style = '',
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            style_type,
        ))

        conn.commit()
        print("DEBUG encrypted reply style updated:", bot_id, chat_id, style_type)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_reply_style_settings shell:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除回覆風格設定
# =========================
def delete_reply_style_settings(bot_id, chat_id, style_type=None, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)

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

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_reply_style_settings:", e)
        raise

    finally:
        conn.close()

    if user_id:
        if style_type:
            delete_encrypted_payload(user_id, bot_id, chat_id, "reply_style_settings", style_type)
        else:
            delete_encrypted_payload(user_id, bot_id, chat_id, "reply_style_settings", "chat")
            delete_encrypted_payload(user_id, bot_id, chat_id, "reply_style_settings", "theater")

    print("DEBUG reply style deleted:", bot_id, chat_id, style_type)
