import random
from typing import Any, Dict, List, Optional

from services.database import get_conn
from services.telegram_service import download_file_bytes


def _text(value: Any) -> str:
    return str(value or "").strip()


def init_image_tables() -> None:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_image_assets (
            id SERIAL PRIMARY KEY,
            image_code TEXT NOT NULL UNIQUE,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            owner_user_id TEXT,
            file_id TEXT NOT NULL,
            file_unique_id TEXT,
            telegram_message_id INTEGER,
            source_type TEXT NOT NULL DEFAULT 'user_upload',
            width INTEGER,
            height INTEGER,
            alias TEXT,
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_image_assets_scope ON chat_image_assets (bot_id, chat_id, is_deleted, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_image_assets_unique ON chat_image_assets (bot_id, chat_id, file_unique_id)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_image_assets_message_unique ON chat_image_assets (bot_id, chat_id, telegram_message_id) WHERE telegram_message_id IS NOT NULL")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_generation_jobs (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            action_id INTEGER,
            gender TEXT NOT NULL,
            generation_mode TEXT NOT NULL,
            prompt_mode TEXT NOT NULL,
            source_choice TEXT,
            fixed_tag TEXT,
            reference_type TEXT NOT NULL,
            reference_code TEXT,
            has_custom_upload BOOLEAN DEFAULT FALSE,
            source_prompt TEXT,
            final_prompt TEXT,
            prompt_generation_status TEXT DEFAULT 'pending',
            prompt_model TEXT,
            prompt_error TEXT,
            prompt_chars_before INTEGER,
            prompt_chars_after INTEGER,
            status_message_id INTEGER,
            status TEXT NOT NULL DEFAULT 'created',
            horde_request_id TEXT,
            api_slot TEXT,
            wait_time INTEGER,
            queue_position INTEGER,
            cancel_requested BOOLEAN DEFAULT FALSE,
            queued_notified BOOLEAN DEFAULT FALSE,
            processing_notified BOOLEAN DEFAULT FALSE,
            worker_token TEXT,
            heartbeat_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS source_prompt TEXT")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS prompt_generation_status TEXT DEFAULT 'pending'")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS prompt_model TEXT")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS prompt_error TEXT")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS prompt_chars_before INTEGER")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS prompt_chars_after INTEGER")
        cursor.execute("ALTER TABLE image_generation_jobs ADD COLUMN IF NOT EXISTS status_message_id INTEGER")
        cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'image_generation_jobs'
                  AND column_name = 'api_slot'
                  AND data_type <> 'text'
            ) THEN
                ALTER TABLE image_generation_jobs
                ALTER COLUMN api_slot TYPE TEXT
                USING api_slot::TEXT;
            END IF;
        END $$
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_jobs_user_active ON image_generation_jobs (user_id, status, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_jobs_recovery ON image_generation_jobs (status, heartbeat_at, created_at)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _new_code(cursor) -> str:
    for _ in range(50):
        code = f"{random.randint(0, 99_999_999):08d}"
        cursor.execute("SELECT 1 FROM chat_image_assets WHERE image_code = %s", (code,))
        if not cursor.fetchone():
            return code
    raise RuntimeError("無法產生圖片代號")


def save_image_asset(
    bot_id: Any,
    chat_id: Any,
    owner_user_id: Any,
    file_id: str,
    file_unique_id: Optional[str],
    telegram_message_id: Optional[int],
    source_type: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not file_id:
        return None

    bot_id = _text(bot_id)
    chat_id = _text(chat_id)
    owner_user_id = _text(owner_user_id)
    file_unique_id = _text(file_unique_id)

    conn = get_conn()
    try:
        cursor = conn.cursor()

        if telegram_message_id:
            cursor.execute("""
                SELECT id, image_code FROM chat_image_assets
                WHERE bot_id=%s AND chat_id=%s AND telegram_message_id=%s
                LIMIT 1
            """, (bot_id, chat_id, int(telegram_message_id)))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "image_code": row[1]}

        if file_unique_id:
            cursor.execute("""
                SELECT id, image_code FROM chat_image_assets
                WHERE bot_id=%s AND chat_id=%s AND file_unique_id=%s AND is_deleted=FALSE
                ORDER BY id DESC LIMIT 1
            """, (bot_id, chat_id, file_unique_id))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE chat_image_assets
                    SET file_id=%s,
                        telegram_message_id=COALESCE(%s, telegram_message_id),
                        owner_user_id=COALESCE(NULLIF(%s, ''), owner_user_id),
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s
                """, (file_id, telegram_message_id, owner_user_id, row[0]))
                conn.commit()
                return {"id": row[0], "image_code": row[1]}

        code = _new_code(cursor)
        cursor.execute("""
            INSERT INTO chat_image_assets (
                image_code, bot_id, chat_id, owner_user_id,
                file_id, file_unique_id, telegram_message_id,
                source_type, width, height
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            code, bot_id, chat_id, owner_user_id,
            file_id, file_unique_id or None, telegram_message_id,
            _text(source_type) or "user_upload", width, height,
        ))
        row = cursor.fetchone()
        conn.commit()
        return {"id": row[0], "image_code": code} if row else None
    except Exception as exc:
        conn.rollback()
        print("IMAGE ASSET SAVE ERROR:", exc, flush=True)
        return None
    finally:
        conn.close()


def save_incoming_photo_message(user_id: Any, bot_id: Any, chat_id: Any, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    photos = (message or {}).get("photo") or []
    if not photos:
        return None
    photo = photos[-1] or {}
    return save_image_asset(
        bot_id=bot_id,
        chat_id=chat_id,
        owner_user_id=user_id,
        file_id=photo.get("file_id"),
        file_unique_id=photo.get("file_unique_id"),
        telegram_message_id=(message or {}).get("message_id"),
        source_type="user_upload",
        width=photo.get("width"),
        height=photo.get("height"),
    )


def list_image_assets(bot_id: Any, chat_id: Any, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, image_code, owner_user_id, file_id, file_unique_id,
                   telegram_message_id, source_type, width, height, alias, created_at
            FROM chat_image_assets
            WHERE bot_id=%s AND chat_id=%s AND is_deleted=FALSE
            ORDER BY created_at DESC, id DESC
            LIMIT %s
        """, (_text(bot_id), _text(chat_id), int(limit)))
        rows = cursor.fetchall()
        return [{
            "id": r[0], "image_code": r[1], "owner_user_id": r[2],
            "file_id": r[3], "file_unique_id": r[4], "telegram_message_id": r[5],
            "source_type": r[6], "width": r[7], "height": r[8],
            "alias": r[9] or "", "created_at": r[10],
        } for r in rows]
    finally:
        conn.close()


def get_image_asset(identifier: Any, bot_id: Any, chat_id: Any) -> Optional[Dict[str, Any]]:
    value = _text(identifier)
    if not value:
        return None
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, image_code, owner_user_id, file_id, file_unique_id,
                   telegram_message_id, source_type, width, height, alias, created_at
            FROM chat_image_assets
            WHERE bot_id=%s AND chat_id=%s AND is_deleted=FALSE
              AND (image_code=%s OR LOWER(COALESCE(alias,''))=LOWER(%s))
            ORDER BY CASE WHEN image_code=%s THEN 0 ELSE 1 END, id DESC
            LIMIT 1
        """, (_text(bot_id), _text(chat_id), value, value, value))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "id": r[0], "image_code": r[1], "owner_user_id": r[2],
            "file_id": r[3], "file_unique_id": r[4], "telegram_message_id": r[5],
            "source_type": r[6], "width": r[7], "height": r[8],
            "alias": r[9] or "", "created_at": r[10],
        }
    finally:
        conn.close()


def download_image_asset(identifier: Any, bot_id: Any, chat_id: Any):
    item = get_image_asset(identifier, bot_id, chat_id)
    if not item:
        return None
    media = download_file_bytes(bot_id, item.get("file_id"))
    if not media:
        return None
    media["asset"] = item
    return media


def rename_image_asset(identifier: Any, alias: str, bot_id: Any, chat_id: Any) -> Dict[str, Any]:
    alias = _text(alias)[:60]
    item = get_image_asset(identifier, bot_id, chat_id)
    if not item:
        return {"ok": False, "message": "找不到圖片"}
    conn = get_conn()
    try:
        cursor = conn.cursor()
        if alias:
            cursor.execute("""
                SELECT 1 FROM chat_image_assets
                WHERE bot_id=%s AND chat_id=%s AND is_deleted=FALSE
                  AND LOWER(COALESCE(alias,''))=LOWER(%s) AND id<>%s
                LIMIT 1
            """, (_text(bot_id), _text(chat_id), alias, item["id"]))
            if cursor.fetchone():
                return {"ok": False, "message": "這個名稱已被其他圖片使用"}
        cursor.execute("UPDATE chat_image_assets SET alias=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (alias or None, item["id"]))
        conn.commit()
        return {"ok": True, "message": "圖片名稱已更新"}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": f"更新失敗：{exc}"}
    finally:
        conn.close()


def delete_image_asset(identifier: Any, bot_id: Any, chat_id: Any) -> bool:
    item = get_image_asset(identifier, bot_id, chat_id)
    if not item:
        return False
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_image_assets SET is_deleted=TRUE, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (item["id"],))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
