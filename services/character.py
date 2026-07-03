from hashlib import sha256
import json

from services.database import get_conn
from services.encrypted_store import delete_encrypted_payload, get_encrypted_payload, save_encrypted_payload
from services.privacy_session import get_current_user_id, get_unlock_code


# =========================
# 預設劇本設定
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
    "user_other_settings": "",

    "opening_sent": False,
    "script_hash": ""
}


# =========================
# 會影響「是否重新回到未開場」的劇本欄位
# =========================
SCRIPT_HASH_KEYS = [
    "ai_name",
    "ai_gender",
    "ai_appearance",
    "story_background",
    "ai_opening",
    "user_gender",
    "user_appearance",
    "user_other_settings"
]


def _text_id(value):
    return str(value)


def _clean_text(value):
    return str(value or "").strip()


def _resolve_user_id(user_id=None):
    return _text_id(user_id) if user_id is not None else get_current_user_id()


def _get_code(user_id, bot_id):
    return get_unlock_code(user_id, bot_id)


# =========================
# 建立劇本指紋
# =========================
def build_script_hash(settings):

    payload = {}

    for key in SCRIPT_HASH_KEYS:
        payload[key] = _clean_text(settings.get(key, ""))

    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True
    )

    return sha256(raw.encode("utf-8")).hexdigest()


# =========================
# 取得人物模式
# =========================
def get_character_mode(bot_id, chat_id, user_id=None):

    settings = get_character_settings(bot_id, chat_id, user_id=user_id)

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
# 讀取舊表殼資料
# =========================
def _get_legacy_character_row(bot_id, chat_id):
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
                user_other_settings,
                opening_sent,
                script_hash
            FROM character_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "mode": row[0] or "聊天模式",
            "ai_name": row[1] or "",
            "ai_gender": row[2] or "",
            "ai_appearance": row[3] or "",
            "story_background": row[4] or "",
            "ai_opening": row[5] or "",
            "user_gender": row[6] or "",
            "user_appearance": row[7] or "",
            "user_other_settings": row[8] or "",
            "opening_sent": bool(row[9]),
            "script_hash": row[10] or ""
        }

    finally:
        conn.close()


# =========================
# 取得完整劇本設定（優先讀加密）
# =========================
def get_character_settings(bot_id, chat_id, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)

    legacy = _get_legacy_character_row(bot_id, chat_id) or DEFAULT_CHARACTER_SETTINGS.copy()
    unlock_code = _get_code(user_id, bot_id)

    if user_id and unlock_code:
        try:
            payload = get_encrypted_payload(
                user_id=user_id,
                bot_id=bot_id,
                chat_id=chat_id,
                data_type="character_settings",
                unlock_code=unlock_code,
                record_key="default",
            )

            if payload:
                result = DEFAULT_CHARACTER_SETTINGS.copy()
                result.update(payload)
                # mode / opening 狀態以舊表殼為準，避免按鈕狀態失效。
                result["mode"] = legacy.get("mode") or result.get("mode") or "聊天模式"
                result["opening_sent"] = bool(legacy.get("opening_sent", result.get("opening_sent", False)))
                result["script_hash"] = legacy.get("script_hash") or result.get("script_hash") or ""
                return result

        except Exception as e:
            print("DECRYPT ERROR get_character_settings:", e)

    return legacy


# =========================
# 取得開場白狀態
# =========================
def get_script_opening_status(bot_id, chat_id, user_id=None):

    settings = get_character_settings(bot_id, chat_id, user_id=user_id)
    opening_text = _clean_text(settings.get("ai_opening", ""))

    if not opening_text:
        return {
            "status": "no_opening",
            "button_text": "▶️ 開始劇本 | 無開場白",
            "opening_text": "",
            "opening_sent": False
        }

    opening_sent = bool(settings.get("opening_sent", False))

    if opening_sent:
        return {
            "status": "started",
            "button_text": "▶️ 開始劇本 | 已開場",
            "opening_text": opening_text,
            "opening_sent": True
        }

    return {
        "status": "not_started",
        "button_text": "▶️ 開始劇本 | 未開場",
        "opening_text": opening_text,
        "opening_sent": False
    }


# =========================
# 標記劇本已經送出開場白
# =========================
def mark_script_opening_sent(bot_id, chat_id):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    settings = get_character_settings(bot_id, chat_id)
    script_hash = settings.get("script_hash") or build_script_hash(settings)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE character_settings
            SET
                opening_sent = TRUE,
                script_hash = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            script_hash,
            bot_id,
            chat_id
        ))

        conn.commit()

        print("DEBUG script opening marked sent:", bot_id, chat_id)

    except Exception as e:
        conn.rollback()
        print("DB ERROR mark_script_opening_sent:", e)
        raise

    finally:
        conn.close()


# =========================
# 更新完整劇本設定（加密寫入，舊表只留模式與狀態）
# =========================
def update_character_settings(bot_id, chat_id, settings, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_code(user_id, bot_id)

    if not user_id or not unlock_code:
        raise ValueError("尚未解鎖資料庫密碼，無法儲存劇本設定")

    mode = settings.get("mode", "聊天模式")
    new_hash = build_script_hash(settings)
    old_hash = ""
    old_opening_sent = False

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT script_hash, opening_sent
            FROM character_settings
            WHERE bot_id = %s
              AND chat_id = %s
        """, (
            bot_id,
            chat_id
        ))

        row = cursor.fetchone()

        if row:
            old_hash = row[0] or ""
            old_opening_sent = bool(row[1])

    finally:
        conn.close()

    opening_sent = old_opening_sent if old_hash == new_hash else False

    payload = {
        "mode": mode,
        "ai_name": settings.get("ai_name", ""),
        "ai_gender": settings.get("ai_gender", ""),
        "ai_appearance": settings.get("ai_appearance", ""),
        "story_background": settings.get("story_background", ""),
        "ai_opening": settings.get("ai_opening", ""),
        "user_gender": settings.get("user_gender", ""),
        "user_appearance": settings.get("user_appearance", ""),
        "user_other_settings": settings.get("user_other_settings", ""),
        "opening_sent": opening_sent,
        "script_hash": new_hash,
    }

    save_encrypted_payload(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        data_type="character_settings",
        unlock_code=unlock_code,
        payload=payload,
        record_key="default",
    )

    # 舊表保留 mode / opening_sent / script_hash，清空敏感欄位。
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
                reply_style,
                user_gender,
                user_appearance,
                user_other_settings,
                opening_sent,
                script_hash,
                updated_at
            )
            VALUES (
                %s, %s, %s,
                '', '', '', '', '', '', '', '', '',
                %s, %s,
                CURRENT_TIMESTAMP
            )

            ON CONFLICT (bot_id, chat_id)

            DO UPDATE SET
                mode = EXCLUDED.mode,
                ai_name = '',
                ai_gender = '',
                ai_appearance = '',
                story_background = '',
                ai_opening = '',
                reply_style = '',
                user_gender = '',
                user_appearance = '',
                user_other_settings = '',
                opening_sent = EXCLUDED.opening_sent,
                script_hash = EXCLUDED.script_hash,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            mode,
            opening_sent,
            new_hash
        ))

        conn.commit()

        print("DEBUG encrypted character settings updated:", bot_id, chat_id, "opening_sent=", opening_sent)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_character_settings shell:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除劇本設定
# =========================
def delete_character_settings(bot_id, chat_id, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = _resolve_user_id(user_id)

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

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_character_settings:", e)
        raise

    finally:
        conn.close()

    if user_id:
        delete_encrypted_payload(user_id, bot_id, chat_id, "character_settings", "default")

    print("DEBUG character settings deleted:", bot_id, chat_id)
