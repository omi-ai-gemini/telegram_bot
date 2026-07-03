import json
from typing import Any

from psycopg2.extras import Json

from services.crypto_box import build_aad, encrypt_payload
from services.database import get_conn


def _text_id(value: Any) -> str:
    return str(value)


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _save_payload(cursor, user_id, bot_id, chat_id, data_type, record_key, unlock_code, payload):
    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    data_type = _text_id(data_type)
    record_key = _text_id(record_key or "default")

    aad = build_aad(user_id, bot_id, chat_id, data_type, record_key)
    encrypted_payload = encrypt_payload(unlock_code, payload, aad=aad)

    cursor.execute(
        """
        INSERT INTO encrypted_settings (
            user_id,
            bot_id,
            chat_id,
            data_type,
            record_key,
            encrypted_payload,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

        ON CONFLICT (user_id, bot_id, chat_id, data_type, record_key)

        DO UPDATE SET
            encrypted_payload = EXCLUDED.encrypted_payload,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            bot_id,
            chat_id,
            data_type,
            record_key,
            Json(encrypted_payload),
        ),
    )


def migrate_plaintext_to_encrypted(user_id: Any, bot_id: Any, chat_id: Any, unlock_code: str) -> None:
    """
    把目前 user / bot / chat 底下仍存在舊表的明文搬進 encrypted_settings，然後清空或刪除舊明文。

    這個函式是安全的：
    - 沒有 unlock_code 不執行
    - 每次解鎖後可重複呼叫
    - 已經搬過且舊表已清空時不會做事
    """

    if not user_id or not bot_id or not chat_id or not unlock_code:
        return

    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = "group" if int(chat_id) < 0 else "private"

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # =========================
        # 舊短期記憶 → encrypted_settings
        # =========================
        if scope == "group":
            cursor.execute(
                """
                SELECT id, role, text, created_at
                FROM chat_memory
                WHERE chat_id = %s
                  AND scope = %s
                ORDER BY id ASC
                """,
                (chat_id, scope),
            )
        else:
            cursor.execute(
                """
                SELECT id, role, text, created_at
                FROM chat_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
                ORDER BY id ASC
                """,
                (bot_id, chat_id, scope),
            )

        chat_rows = cursor.fetchall()

        for row in chat_rows:
            legacy_id, role, text, created_at = row
            if not _has_text(text):
                continue

            _save_payload(
                cursor,
                user_id,
                bot_id,
                chat_id,
                "chat_memory",
                f"legacy_chat_{legacy_id}",
                unlock_code,
                {
                    "role": role or "user",
                    "text": text or "",
                    "scope": scope,
                    "legacy_id": legacy_id,
                    "legacy_created_at": str(created_at) if created_at else "",
                },
            )

        if chat_rows:
            if scope == "group":
                cursor.execute(
                    """
                    DELETE FROM chat_memory
                    WHERE chat_id = %s
                      AND scope = %s
                    """,
                    (chat_id, scope),
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM chat_memory
                    WHERE bot_id = %s
                      AND chat_id = %s
                      AND scope = %s
                    """,
                    (bot_id, chat_id, scope),
                )

        # =========================
        # 舊長期記憶 → encrypted_settings
        # =========================
        if scope == "group":
            cursor.execute(
                """
                SELECT id, fact, created_at
                FROM facts_memory
                WHERE chat_id = %s
                  AND scope = %s
                ORDER BY id ASC
                """,
                (chat_id, scope),
            )
        else:
            cursor.execute(
                """
                SELECT id, fact, created_at
                FROM facts_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
                ORDER BY id ASC
                """,
                (bot_id, chat_id, scope),
            )

        fact_rows = cursor.fetchall()

        for row in fact_rows:
            legacy_id, fact, created_at = row
            if not _has_text(fact):
                continue

            _save_payload(
                cursor,
                user_id,
                bot_id,
                chat_id,
                "facts_memory",
                f"legacy_fact_{legacy_id}",
                unlock_code,
                {
                    "fact": fact or "",
                    "scope": scope,
                    "legacy_id": legacy_id,
                    "legacy_created_at": str(created_at) if created_at else "",
                },
            )

        if fact_rows:
            if scope == "group":
                cursor.execute(
                    """
                    DELETE FROM facts_memory
                    WHERE chat_id = %s
                      AND scope = %s
                    """,
                    (chat_id, scope),
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM facts_memory
                    WHERE bot_id = %s
                      AND chat_id = %s
                      AND scope = %s
                    """,
                    (bot_id, chat_id, scope),
                )

        # =========================
        # 聊天人物設定 → encrypted_settings
        # =========================
        cursor.execute(
            """
            SELECT persona_name, persona_gender, persona_background
            FROM chat_persona_settings
            WHERE bot_id = %s
              AND chat_id = %s
            """,
            (bot_id, chat_id),
        )
        row = cursor.fetchone()

        if row and any(_has_text(v) for v in row):
            _save_payload(
                cursor,
                user_id,
                bot_id,
                chat_id,
                "chat_persona_settings",
                "default",
                unlock_code,
                {
                    "persona_name": row[0] or "",
                    "persona_gender": row[1] or "",
                    "persona_background": row[2] or "",
                },
            )

            cursor.execute(
                """
                UPDATE chat_persona_settings
                SET persona_name = '',
                    persona_gender = '',
                    persona_background = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE bot_id = %s
                  AND chat_id = %s
                """,
                (bot_id, chat_id),
            )

        # =========================
        # 劇本設定 → encrypted_settings
        # =========================
        cursor.execute(
            """
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
            """,
            (bot_id, chat_id),
        )
        row = cursor.fetchone()

        if row and any(_has_text(v) for v in row[1:9]):
            _save_payload(
                cursor,
                user_id,
                bot_id,
                chat_id,
                "character_settings",
                "default",
                unlock_code,
                {
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
                    "script_hash": row[10] or "",
                },
            )

            cursor.execute(
                """
                UPDATE character_settings
                SET ai_name = '',
                    ai_gender = '',
                    ai_appearance = '',
                    story_background = '',
                    ai_opening = '',
                    reply_style = '',
                    user_gender = '',
                    user_appearance = '',
                    user_other_settings = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE bot_id = %s
                  AND chat_id = %s
                """,
                (bot_id, chat_id),
            )

        # =========================
        # 回覆風格設定 → encrypted_settings
        # =========================
        cursor.execute(
            """
            SELECT style_type, reply_style
            FROM reply_style_settings
            WHERE bot_id = %s
              AND chat_id = %s
            """,
            (bot_id, chat_id),
        )
        rows = cursor.fetchall()

        for style_type, reply_style in rows:
            if not _has_text(reply_style):
                continue

            _save_payload(
                cursor,
                user_id,
                bot_id,
                chat_id,
                "reply_style_settings",
                style_type or "chat",
                unlock_code,
                {
                    "style_type": style_type or "chat",
                    "reply_style": reply_style or "",
                },
            )

        cursor.execute(
            """
            UPDATE reply_style_settings
            SET reply_style = '',
                updated_at = CURRENT_TIMESTAMP
            WHERE bot_id = %s
              AND chat_id = %s
            """,
            (bot_id, chat_id),
        )

        conn.commit()

    except Exception as exc:
        conn.rollback()
        print("DB ERROR migrate_plaintext_to_encrypted:", exc)
        raise

    finally:
        conn.close()
