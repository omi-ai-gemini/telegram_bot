from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for
from services.runtime_cache import get_cache, set_cache, delete_cache


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


def _cache_key(bot_id, chat_id, style_type=None):
    if style_type is None:
        return ("reply_style_settings", _text_id(bot_id), _text_id(chat_id))

    return ("reply_style_settings", _text_id(bot_id), _text_id(chat_id), normalize_style_type(style_type))


def clear_reply_style_settings_cache(bot_id, chat_id, style_type=None):
    delete_cache(_cache_key(bot_id, chat_id, style_type))


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
    cache_key = _cache_key(bot_id, chat_id, style_type)

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

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
            settings = {
                "style_type": style_type,
                "reply_style": _decrypt_style(bot_id, chat_id, style_type, row[0])
            }
            return set_cache(cache_key, settings, ttl=60)

        legacy_reply_style = _get_legacy_reply_style(
            cursor,
            bot_id,
            chat_id,
            style_type
        )

        settings = {
            "style_type": style_type,
            "reply_style": legacy_reply_style or ""
        }
        return set_cache(cache_key, settings, ttl=60)

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
        clear_reply_style_settings_cache(bot_id, chat_id, style_type)

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
        clear_reply_style_settings_cache(bot_id, chat_id, style_type)

        print("DEBUG reply style deleted:", bot_id, chat_id, style_type)

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_reply_style_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 相容舊流程：重新儲存既有回覆風格
# =========================
def resave_existing_reply_style_settings(bot_id, chat_id, style_type=None, user_id=None):
    """
    給 ai_actions.py 的「🗣️ 重跑前重新儲存自訂風格」流程使用。

    目的：
    - 不改使用者已經自訂好的內容。
    - 只是把目前 DB 內的 reply_style 讀出來，再走一次 update_reply_style_settings()。
    - 可讓新加密 / 新 AAD / 新預設前綴流程重新套用。

    style_type 可傳：
    - chat / 聊天模式
    - theater / 劇場模式
    - None：兩種模式都嘗試重存
    """
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    style_types = [normalize_style_type(style_type)] if style_type else ["chat", "theater"]
    changed = False

    for item_style_type in style_types:
        try:
            settings = get_reply_style_settings(
                bot_id=bot_id,
                chat_id=chat_id,
                style_type=item_style_type,
                user_id=user_id,
            )

            reply_style = str((settings or {}).get("reply_style") or "")

            # 沒有自訂內容就不要硬寫入，避免把空資料洗進 DB。
            if not reply_style.strip():
                clear_reply_style_settings_cache(bot_id, chat_id, item_style_type)
                continue

            update_reply_style_settings(
                bot_id=bot_id,
                chat_id=chat_id,
                style_type=item_style_type,
                reply_style=reply_style,
                user_id=user_id,
            )
            changed = True

        except Exception as exc:
            print("DB ERROR resave_existing_reply_style_settings:", item_style_type, exc, flush=True)

    return changed
