"""
把既有明文欄位轉成 ENCv1 密文。

使用前必須設定：
- DATABASE_URL
- APP_ENCRYPTION_SECRET

測試：
python tools/encrypt_existing_plaintext.py --dry-run

正式：
python tools/encrypt_existing_plaintext.py
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.crypto_env import encrypt_text, is_encrypted, aad_for
from services.database import get_conn


def _has_value(value):
    return bool(str(value or "").strip())


def migrate_chat_memory(cursor, dry_run=False):
    cursor.execute("""
        SELECT id, bot_id, chat_id, scope, role, text
        FROM chat_memory
        WHERE text IS NOT NULL
    """)
    rows = cursor.fetchall()
    count = 0

    for row_id, bot_id, chat_id, scope, role, text in rows:
        if not _has_value(text) or is_encrypted(text):
            continue

        role = role or "user"
        aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
        encrypted = encrypt_text(text, aad=aad)

        if not dry_run:
            cursor.execute("""
                UPDATE chat_memory
                SET text = %s
                WHERE id = %s
            """, (encrypted, row_id))

        count += 1

    return count


def migrate_facts_memory(cursor, dry_run=False):
    cursor.execute("""
        SELECT id, bot_id, chat_id, scope, fact
        FROM facts_memory
        WHERE fact IS NOT NULL
    """)
    rows = cursor.fetchall()
    count = 0

    for row_id, bot_id, chat_id, scope, fact in rows:
        if not _has_value(fact) or is_encrypted(fact):
            continue

        aad = aad_for("facts_memory", "fact", bot_id, chat_id, scope)
        encrypted = encrypt_text(fact, aad=aad)

        if not dry_run:
            cursor.execute("""
                UPDATE facts_memory
                SET fact = %s
                WHERE id = %s
            """, (encrypted, row_id))

        count += 1

    return count


def migrate_character_settings(cursor, dry_run=False):
    fields = [
        "ai_name",
        "ai_gender",
        "ai_appearance",
        "story_background",
        "ai_opening",
        "user_gender",
        "user_appearance",
        "user_other_settings",
    ]

    cursor.execute("""
        SELECT bot_id, chat_id,
               ai_name, ai_gender, ai_appearance, story_background, ai_opening,
               user_gender, user_appearance, user_other_settings
        FROM character_settings
    """)
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        bot_id = row[0]
        chat_id = row[1]
        values = dict(zip(fields, row[2:]))
        updates = {}

        for field, value in values.items():
            if not _has_value(value) or is_encrypted(value):
                continue

            aad = aad_for("character_settings", field, bot_id, chat_id)
            updates[field] = encrypt_text(value, aad=aad)

        if updates:
            if not dry_run:
                set_sql = ", ".join([f"{field} = %s" for field in updates])
                params = list(updates.values()) + [bot_id, chat_id]
                cursor.execute(f"""
                    UPDATE character_settings
                    SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                    WHERE bot_id = %s
                      AND chat_id = %s
                """, params)

            count += len(updates)

    return count


def migrate_chat_persona_settings(cursor, dry_run=False):
    fields = ["persona_name", "persona_gender", "persona_background"]

    cursor.execute("""
        SELECT bot_id, chat_id, persona_name, persona_gender, persona_background
        FROM chat_persona_settings
    """)
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        bot_id = row[0]
        chat_id = row[1]
        values = dict(zip(fields, row[2:]))
        updates = {}

        for field, value in values.items():
            if not _has_value(value) or is_encrypted(value):
                continue

            aad = aad_for("chat_persona_settings", field, bot_id, chat_id)
            updates[field] = encrypt_text(value, aad=aad)

        if updates:
            if not dry_run:
                set_sql = ", ".join([f"{field} = %s" for field in updates])
                params = list(updates.values()) + [bot_id, chat_id]
                cursor.execute(f"""
                    UPDATE chat_persona_settings
                    SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                    WHERE bot_id = %s
                      AND chat_id = %s
                """, params)

            count += len(updates)

    return count


def migrate_reply_style_settings(cursor, dry_run=False):
    cursor.execute("""
        SELECT bot_id, chat_id, style_type, reply_style
        FROM reply_style_settings
        WHERE reply_style IS NOT NULL
    """)
    rows = cursor.fetchall()
    count = 0

    for bot_id, chat_id, style_type, reply_style in rows:
        if not _has_value(reply_style) or is_encrypted(reply_style):
            continue

        aad = aad_for("reply_style_settings", "reply_style", bot_id, chat_id, style_type)
        encrypted = encrypt_text(reply_style, aad=aad)

        if not dry_run:
            cursor.execute("""
                UPDATE reply_style_settings
                SET reply_style = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND style_type = %s
            """, (encrypted, bot_id, chat_id, style_type))

        count += 1

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_conn()

    try:
        cursor = conn.cursor()

        counts = {
            "chat_memory.text": migrate_chat_memory(cursor, dry_run=args.dry_run),
            "facts_memory.fact": migrate_facts_memory(cursor, dry_run=args.dry_run),
            "character_settings fields": migrate_character_settings(cursor, dry_run=args.dry_run),
            "chat_persona_settings fields": migrate_chat_persona_settings(cursor, dry_run=args.dry_run),
            "reply_style_settings.reply_style": migrate_reply_style_settings(cursor, dry_run=args.dry_run),
        }

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

        print("DRY RUN" if args.dry_run else "DONE")
        for name, count in counts.items():
            print(f"{name}: {count}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
