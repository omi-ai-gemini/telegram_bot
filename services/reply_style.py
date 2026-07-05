from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for


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


def _decrypt_style(bot_id, chat_id, style_type, value):
    aad = aad_for("reply_style_settings", "reply_style", bot_id, chat_id, style_type)
    try:
        return decrypt_text(value, aad=aad)
    except Exception as exc:
        print("DECRYPT ERROR reply_style:", exc)
        return ""


def _encrypt_style(bot_id, chat_id, style_type, value):
    aad = aad_for("reply_style_settings", "reply_style", bot_id, chat_id, style_type)
    return encrypt_text(value, aad=aad)


def _decrypt_legacy_style(table_name, bot_id, chat_id, value):
    aad = aad_for(table_name, "reply_style", bot_id, chat_id)
    try:
        return decrypt_text(value, aad=aad)
    except Exception:
        # 舊資料可能沒有用相同 aad 加密，當成空值避免報錯中斷。
        return ""


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
            table_name = "character_settings"
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
            table_name = "chat_persona_settings"

        row = cursor.fetchone()

        if row and row[0]:
            return _decrypt_legacy_style(table_name, bot_id, chat_id, row[0])

    except Exception as e:
        # 舊欄位不存在時會進來，這是正常過渡狀況
        print("DEBUG legacy reply_style not available:", e)

    return ""


# =========================
# 取得回覆風格設定
# =========================
def get_reply_style_settings(bot_id, chat_id, style_type="chat", user_id=None):

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
                "reply_style": _decrypt_style(bot_id, chat_id, style_type, row[0])
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
# 更新回覆風格設定
# 敏感欄位直接加密後存回原本 reply_style_settings.reply_style。
# =========================
def update_reply_style_settings(bot_id, chat_id, style_type, reply_style, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    style_type = normalize_style_type(style_type)
    encrypted_reply_style = _encrypt_style(bot_id, chat_id, style_type, reply_style or "")

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
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id, style_type)

            DO UPDATE SET
                reply_style = EXCLUDED.reply_style,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            style_type,
            encrypted_reply_style
        ))

        conn.commit()

        print("DEBUG encrypted reply style updated:", bot_id, chat_id, style_type)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_reply_style_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除回覆風格設定
# =========================
def delete_reply_style_settings(bot_id, chat_id, style_type=None, user_id=None):

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

# =========================
# 重新儲存既有自訂回覆風格
# - 給 /hidden 🗣️ 除錯回覆使用
# - 只重存已存在的 reply_style_settings 資料
# - 不建立新資料、不回填預設風格、不覆蓋成預設文字
# =========================
def resave_existing_reply_style_settings(bot_id, chat_id, style_type=None, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    if style_type:
        style_types = [normalize_style_type(style_type)]
    else:
        style_types = ["chat", "theater"]

    conn = get_conn()
    updated_count = 0

    try:
        cursor = conn.cursor()

        for current_style_type in style_types:
            cursor.execute("""
                SELECT reply_style
                FROM reply_style_settings
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND style_type = %s
                LIMIT 1
            """, (
                bot_id,
                chat_id,
                current_style_type
            ))

            row = cursor.fetchone()

            if not row:
                continue

            # 讀出使用者已經自訂好的風格，再用目前加密流程原樣寫回。
            # 不使用 DEFAULT，也不從預設風格產生新資料。
            current_reply_style = _decrypt_style(
                bot_id,
                chat_id,
                current_style_type,
                row[0]
            )

            encrypted_reply_style = _encrypt_style(
                bot_id,
                chat_id,
                current_style_type,
                current_reply_style
            )

            cursor.execute("""
                UPDATE reply_style_settings
                SET reply_style = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND style_type = %s
            """, (
                encrypted_reply_style,
                bot_id,
                chat_id,
                current_style_type
            ))

            updated_count += cursor.rowcount or 0

        conn.commit()

        print(
            "DEBUG existing reply style resaved:",
            bot_id,
            chat_id,
            style_types,
            "updated=",
            updated_count,
            flush=True
        )

        return updated_count

    except Exception as e:
        conn.rollback()
        print("DB ERROR resave_existing_reply_style_settings:", e)
        return 0

    finally:
        conn.close()
