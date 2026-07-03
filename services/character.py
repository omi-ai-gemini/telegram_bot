from hashlib import sha256
import json

from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for


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

ENCRYPTED_CHARACTER_FIELDS = [
    "ai_name",
    "ai_gender",
    "ai_appearance",
    "story_background",
    "ai_opening",
    "user_gender",
    "user_appearance",
    "user_other_settings",
]


def _text_id(value):
    return str(value)


def _clean_text(value):
    return str(value or "").strip()


def _decrypt_field(bot_id, chat_id, field, value):
    aad = aad_for("character_settings", field, bot_id, chat_id)
    try:
        return decrypt_text(value, aad=aad)
    except Exception as exc:
        print("DECRYPT ERROR character field:", field, exc)
        return ""


def _encrypt_field(bot_id, chat_id, field, value):
    aad = aad_for("character_settings", field, bot_id, chat_id)
    return encrypt_text(value, aad=aad)


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
# 取得完整劇本設定
# 敏感欄位在 DB 裡可能是 ENCv1 密文，這裡自動解密。
# 舊明文資料會原樣讀出。
# =========================
def get_character_settings(bot_id, chat_id, user_id=None):

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
            return DEFAULT_CHARACTER_SETTINGS.copy()

        return {
            "mode": row[0] or "聊天模式",
            "ai_name": _decrypt_field(bot_id, chat_id, "ai_name", row[1]),
            "ai_gender": _decrypt_field(bot_id, chat_id, "ai_gender", row[2]),
            "ai_appearance": _decrypt_field(bot_id, chat_id, "ai_appearance", row[3]),
            "story_background": _decrypt_field(bot_id, chat_id, "story_background", row[4]),
            "ai_opening": _decrypt_field(bot_id, chat_id, "ai_opening", row[5]),
            "user_gender": _decrypt_field(bot_id, chat_id, "user_gender", row[6]),
            "user_appearance": _decrypt_field(bot_id, chat_id, "user_appearance", row[7]),
            "user_other_settings": _decrypt_field(bot_id, chat_id, "user_other_settings", row[8]),
            "opening_sent": bool(row[9]),
            "script_hash": row[10] or ""
        }

    except Exception as e:
        print("DB ERROR get_character_settings:", e)
        raise

    finally:
        conn.close()


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
# 更新完整劇本設定
# 敏感欄位直接加密後存回原本 character_settings 欄位。
# =========================
def update_character_settings(bot_id, chat_id, settings, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

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

    encrypted = {
        field: _encrypt_field(bot_id, chat_id, field, settings.get(field, ""))
        for field in ENCRYPTED_CHARACTER_FIELDS
    }

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
                %s, %s, %s, %s, %s, '', %s, %s, %s,
                %s, %s,
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
                reply_style = '',
                user_gender = EXCLUDED.user_gender,
                user_appearance = EXCLUDED.user_appearance,
                user_other_settings = EXCLUDED.user_other_settings,
                opening_sent = EXCLUDED.opening_sent,
                script_hash = EXCLUDED.script_hash,
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            mode,
            encrypted["ai_name"],
            encrypted["ai_gender"],
            encrypted["ai_appearance"],
            encrypted["story_background"],
            encrypted["ai_opening"],
            encrypted["user_gender"],
            encrypted["user_appearance"],
            encrypted["user_other_settings"],
            opening_sent,
            new_hash
        ))

        conn.commit()

        print("DEBUG encrypted character settings updated:", bot_id, chat_id, "opening_sent=", opening_sent)

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_character_settings:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除劇本設定
# =========================
def delete_character_settings(bot_id, chat_id, user_id=None):

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

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_character_settings:", e)
        raise

    finally:
        conn.close()

    print("DEBUG character settings deleted:", bot_id, chat_id)
