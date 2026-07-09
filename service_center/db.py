from services.database import get_conn


# =========================
# 服務中心公告資料庫
# =========================
# - 公告獨立於主遊戲資料表
# - /start 不再主動顯示公告
# - 公告按鈕會依 created_at / id 倒序顯示
# - 每天下午 17:00（Asia/Taipei）如果有新公告，主動推播一次

DEFAULT_ANNOUNCEMENT_KEY = "20260710_media_input_update"
DEFAULT_ANNOUNCEMENT_LABEL = "功能更新"
DEFAULT_ANNOUNCEMENT_TITLE = "圖片與貼圖輸入更新"
DEFAULT_ANNOUNCEMENT_BODY = """本次更新：
1. 新增圖片訊息支援：使用者直接傳圖片時，系統會先解析圖片內容，再交回聊天流程自然回覆。
2. 新增靜態貼圖支援：Telegram 靜態貼圖會被解析成可理解的文字內容，再由 AI 接續回覆。
3. 新增未支援媒體防呆：語音、音訊、影片、GIF、動態貼圖、影片貼圖、文件、位置等目前尚未支援的輸入，會回覆提示，不會再完全沒反應。

提醒：圖片與貼圖解析會使用 Gemini 圖片理解能力，若使用者尚未設定 Gemini API Key，仍會先提示需要完成設定。"""

SCHEDULER_STATE_KEY = "service_center_announcement_daily_push"


def _text_id(value):
    return str(value or "").strip()


def init_service_center_db():
    """建立服務中心專用資料表，並補入本次預設公告。"""
    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_center_announcements (
            id SERIAL PRIMARY KEY,
            ann_key TEXT,
            label TEXT NOT NULL DEFAULT '公告',
            title TEXT NOT NULL DEFAULT '更新公告',
            body TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN DEFAULT TRUE,
            push_enabled BOOLEAN DEFAULT FALSE,
            pushed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 舊表相容：CREATE TABLE IF NOT EXISTS 不會自動補欄位，所以這裡補齊。
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS ann_key TEXT")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS label TEXT NOT NULL DEFAULT '公告'")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '更新公告'")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT ''")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS push_enabled BOOLEAN DEFAULT FALSE")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS pushed_at TIMESTAMP")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE service_center_announcements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_service_center_announcements_active_latest
        ON service_center_announcements (is_active, created_at DESC, id DESC)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_center_subscribers (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            chat_id TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT TRUE,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("ALTER TABLE service_center_subscribers ADD COLUMN IF NOT EXISTS user_id TEXT")
        cursor.execute("ALTER TABLE service_center_subscribers ADD COLUMN IF NOT EXISTS chat_id TEXT")
        cursor.execute("ALTER TABLE service_center_subscribers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cursor.execute("ALTER TABLE service_center_subscribers ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE service_center_subscribers ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_service_center_subscribers_chat_id
        ON service_center_subscribers (chat_id)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_center_announcement_deliveries (
            id SERIAL PRIMARY KEY,
            announcement_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sending',
            error_text TEXT,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (announcement_id, chat_id)
        )
        """)

        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS announcement_id INTEGER")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS chat_id TEXT")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'sending'")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS error_text TEXT")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE service_center_announcement_deliveries ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_service_center_delivery_unique
        ON service_center_announcement_deliveries (announcement_id, chat_id)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_center_scheduler_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 不依賴 ON CONFLICT(ann_key)，避免舊表沒有 unique constraint 時初始化失敗。
        cursor.execute(
            """
            SELECT id
            FROM service_center_announcements
            WHERE ann_key = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (DEFAULT_ANNOUNCEMENT_KEY,),
        )
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE service_center_announcements
                SET label = %s,
                    title = %s,
                    body = %s,
                    is_active = TRUE,
                    push_enabled = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    DEFAULT_ANNOUNCEMENT_LABEL,
                    DEFAULT_ANNOUNCEMENT_TITLE,
                    DEFAULT_ANNOUNCEMENT_BODY,
                    row[0],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO service_center_announcements (
                    ann_key,
                    label,
                    title,
                    body,
                    is_active,
                    push_enabled,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    DEFAULT_ANNOUNCEMENT_KEY,
                    DEFAULT_ANNOUNCEMENT_LABEL,
                    DEFAULT_ANNOUNCEMENT_TITLE,
                    DEFAULT_ANNOUNCEMENT_BODY,
                ),
            )

        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER DB INIT ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def upsert_service_center_subscriber(user_id, chat_id):
    """記錄可推播對象。Telegram 只允許 bot 主動傳給曾經互動過的 chat。"""
    user_id = _text_id(user_id)
    chat_id = _text_id(chat_id)

    if not user_id or not chat_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_center_subscribers (
                user_id,
                chat_id,
                is_active,
                first_seen_at,
                last_seen_at
            )
            VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (chat_id)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                is_active = TRUE,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (user_id, chat_id),
        )
        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER UPSERT SUBSCRIBER ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def mark_service_center_subscriber_inactive(chat_id):
    chat_id = _text_id(chat_id)

    if not chat_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE service_center_subscribers
            SET is_active = FALSE,
                last_seen_at = CURRENT_TIMESTAMP
            WHERE chat_id = %s
            """,
            (chat_id,),
        )
        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER MARK SUBSCRIBER INACTIVE ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def list_service_center_subscribers(limit=1000):
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, chat_id
            FROM service_center_subscribers
            WHERE is_active = TRUE
            ORDER BY last_seen_at DESC, id DESC
            LIMIT %s
            """,
            (int(limit or 1000),),
        )

        rows = cursor.fetchall()
        return [
            {
                "user_id": row[0],
                "chat_id": row[1],
            }
            for row in rows
        ]

    except Exception as exc:
        print("SERVICE CENTER LIST SUBSCRIBERS ERROR:", exc, flush=True)
        return []

    finally:
        conn.close()


def list_announcements(limit=10):
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, label, title, body, created_at
            FROM service_center_announcements
            WHERE is_active = TRUE
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (int(limit or 10),),
        )

        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "label": row[1],
                "title": row[2],
                "body": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    except Exception as exc:
        print("SERVICE CENTER LIST ANNOUNCEMENTS ERROR:", exc, flush=True)
        return []

    finally:
        conn.close()


def list_pushable_announcements(limit=10):
    """取得需要排程推播的公告。每個 chat 是否已推過由 delivery table 控制。"""
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, label, title, body, created_at
            FROM service_center_announcements
            WHERE is_active = TRUE
              AND push_enabled = TRUE
              AND pushed_at IS NULL
            ORDER BY created_at ASC, id ASC
            LIMIT %s
            """,
            (int(limit or 10),),
        )

        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "label": row[1],
                "title": row[2],
                "body": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    except Exception as exc:
        print("SERVICE CENTER LIST PUSHABLE ANNOUNCEMENTS ERROR:", exc, flush=True)
        return []

    finally:
        conn.close()


def get_latest_announcement():
    items = list_announcements(limit=1)
    return items[0] if items else None


def create_announcement(label, title, body, ann_key=None, push_enabled=True):
    """保留給管理員指令或後台使用。預設會在下一次 17:00 主動推播。"""
    label = _text_id(label) or "公告"
    title = _text_id(title) or "更新公告"
    body = _text_id(body)
    ann_key = _text_id(ann_key) or None

    if not body:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_center_announcements (
                ann_key,
                label,
                title,
                body,
                is_active,
                push_enabled,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, TRUE, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (ann_key, label, title, body, bool(push_enabled)),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0] if row else True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER CREATE ANNOUNCEMENT ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def claim_announcement_delivery(announcement_id, chat_id):
    """搶占單一公告對單一 chat 的推播權。成功才送，避免多 worker 重複推。"""
    announcement_id = int(announcement_id)
    chat_id = _text_id(chat_id)

    if not announcement_id or not chat_id:
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_center_announcement_deliveries (
                announcement_id,
                chat_id,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, 'sending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (announcement_id, chat_id)
            DO NOTHING
            RETURNING id
            """,
            (announcement_id, chat_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0] if row else None

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER CLAIM DELIVERY ERROR:", exc, flush=True)
        return None

    finally:
        conn.close()


def mark_announcement_pushed(announcement_id):
    """公告當天排程已處理完後關閉推播，避免未來新 subscriber 又收到舊公告。"""
    try:
        announcement_id = int(announcement_id)
    except Exception:
        return False

    if not announcement_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE service_center_announcements
            SET push_enabled = FALSE,
                pushed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (announcement_id,),
        )
        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER MARK ANNOUNCEMENT PUSHED ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def mark_announcement_delivery_result(delivery_id, ok=True, error_text=None):
    if not delivery_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        if ok:
            cursor.execute(
                """
                UPDATE service_center_announcement_deliveries
                SET status = 'delivered',
                    error_text = NULL,
                    delivered_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (delivery_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE service_center_announcement_deliveries
                SET status = 'failed',
                    error_text = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (_text_id(error_text)[:500], delivery_id),
            )

        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER MARK DELIVERY ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def get_scheduler_state(state_key):
    state_key = _text_id(state_key)

    if not state_key:
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT state_value
            FROM service_center_scheduler_state
            WHERE state_key = %s
            """,
            (state_key,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    except Exception as exc:
        print("SERVICE CENTER GET SCHEDULER STATE ERROR:", exc, flush=True)
        return None

    finally:
        conn.close()


def set_scheduler_state(state_key, state_value):
    state_key = _text_id(state_key)
    state_value = _text_id(state_value)

    if not state_key:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_center_scheduler_state (
                state_key,
                state_value,
                updated_at
            )
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (state_key)
            DO UPDATE SET
                state_value = EXCLUDED.state_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (state_key, state_value),
        )
        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER SET SCHEDULER STATE ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()
