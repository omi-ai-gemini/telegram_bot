from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for


DEFAULT_CHAT_PERSONA_SETTINGS = {
    "persona_name": "",
    "persona_gender": "",
    "persona_background": ""
}

ENCRYPTED_CHAT_PERSONA_FIELDS = [
    "persona_name",
    "persona_gender",
    "persona_background",
]


def _text_id(value):
    return str(value)


def _decrypt_field(bot_id, chat_id, field, value):
    aad = aad_for("chat_persona_settings", field, bot_id, chat_id)
    try:
        return decrypt_text(value, aad=aad)
    except Exception as exc:
        print("DECRYPT ERROR chat_persona field:", field, exc)
        return ""


def _encrypt_field(bot_id, chat_id, field, value):
    aad = aad_for("chat_persona_settings", field, bot_id, chat_id)
    return encrypt_text(value, aad=aad)


# =========================
# 檢查是否有設定聊天人物
# 注意：回覆風格已移到 reply_style_settings，不算聊天人物本體
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
# 敏感欄位在 DB 裡可能是 ENCv1 密文，這裡自動解密。
# =========================
def get_chat_persona_settings(bot_id, chat_id, user_id=None):

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
            "persona_name": _decrypt_field(bot_id, chat_id, "persona_name", row[0]),
            "persona_gender": _decrypt_field(bot_id, chat_id, "persona_gender", row[1]),
            "persona_background": _decrypt_field(bot_id, chat_id, "persona_background", row[2]),
        }

    except Exception as e:
        print("DB ERROR get_chat_persona_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 更新聊天模式人物設定
# 不更新 reply_style，避免換聊天對象時覆蓋獨立風格設定。
# 敏感欄位直接加密後存回原本 chat_persona_settings 欄位。
# =========================
def update_chat_persona_settings(bot_id, chat_id, settings, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    encrypted = {
        field: _encrypt_field(bot_id, chat_id, field, settings.get(field, ""))
        for field in ENCRYPTED_CHAT_PERSONA_FIELDS
    }

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
                reply_style,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, '', CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                persona_name = EXCLUDED.persona_name,
                persona_gender = EXCLUDED.persona_gender,
                persona_background = EXCLUDED.persona_background,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            encrypted["persona_name"],
            encrypted["persona_gender"],
            encrypted["persona_background"],
        ))

        conn.commit()

        print("DEBUG encrypted chat persona updated:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_chat_persona_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除聊天模式人物設定
# =========================
def delete_chat_persona_settings(bot_id, chat_id, user_id=None):

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
