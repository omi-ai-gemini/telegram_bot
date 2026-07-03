from services.database import get_conn
from services.encrypted_store import delete_encrypted_payload, get_encrypted_payload, save_encrypted_payload
from services.privacy_session import get_current_user_id, get_unlock_code


DEFAULT_CHAT_PERSONA_SETTINGS = {
    "persona_name": "",
    "persona_gender": "",
    "persona_background": ""
}


def _text_id(value):
    return str(value)


def _resolve_user_id(user_id=None):
    return _text_id(user_id) if user_id is not None else get_current_user_id()


def _get_code(user_id, bot_id):
    return get_unlock_code(user_id, bot_id)


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
# 取得聊天模式人物設定（優先讀加密）
# =========================
def get_chat_persona_settings(bot_id, chat_id, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_code(user_id, bot_id)

    if user_id and unlock_code:
        try:
            payload = get_encrypted_payload(
                user_id=user_id,
                bot_id=bot_id,
                chat_id=chat_id,
                data_type="chat_persona_settings",
                unlock_code=unlock_code,
                record_key="default",
            )

            if payload:
                return {
                    "persona_name": payload.get("persona_name", "") or "",
                    "persona_gender": payload.get("persona_gender", "") or "",
                    "persona_background": payload.get("persona_background", "") or "",
                }

        except Exception as e:
            print("DECRYPT ERROR get_chat_persona_settings:", e)

    # 舊資料相容：尚未遷移前讀舊表。遷移後舊欄位會被清空。
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
# 更新聊天模式人物設定（加密寫入，舊表只留空殼相容）
# =========================
def update_chat_persona_settings(bot_id, chat_id, settings, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_code(user_id, bot_id)

    if not user_id or not unlock_code:
        raise ValueError("尚未解鎖資料庫密碼，無法儲存聊天人物設定")

    payload = {
        "persona_name": settings.get("persona_name", ""),
        "persona_gender": settings.get("persona_gender", ""),
        "persona_background": settings.get("persona_background", ""),
    }

    save_encrypted_payload(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        data_type="chat_persona_settings",
        unlock_code=unlock_code,
        payload=payload,
        record_key="default",
    )

    # 舊表保留 row 但清空敏感欄位，避免 Supabase 繼續看到明文。
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
            VALUES (%s, %s, '', '', '', CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                persona_name = '',
                persona_gender = '',
                persona_background = '',
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
        ))

        conn.commit()
        print("DEBUG encrypted chat persona updated:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_chat_persona_settings shell:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除聊天模式人物設定
# =========================
def delete_chat_persona_settings(bot_id, chat_id, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)

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

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_chat_persona_settings:", e)
        raise

    finally:
        conn.close()

    if user_id:
        delete_encrypted_payload(user_id, bot_id, chat_id, "chat_persona_settings", "default")

    print("DEBUG chat persona deleted:", bot_id, chat_id)
