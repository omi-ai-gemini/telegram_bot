from services.database import get_conn


# =========================
# 服務中心資料表
# =========================
# 目前只建立公告表。
# 服務中心 bot token 仍然只放 SERVICE_CENTER_BOT_TOKEN，不進 DB。


def init_service_center_db():
    """初始化服務中心專用資料表。"""
    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_center_announcements (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_by_user_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_service_center_announcements_active
        ON service_center_announcements (is_active, id DESC)
        """)

        conn.commit()
        print("SERVICE CENTER DB INIT OK", flush=True)
        return True

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER DB INIT ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def add_announcement(title, body, created_by_user_id=None):
    """新增一筆服務中心公告。"""
    title = str(title or "").strip()
    body = str(body or "").strip()

    if not title:
        title = "公告"

    if not body:
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_center_announcements (
                title,
                body,
                created_by_user_id,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (title, body, str(created_by_user_id or "") or None),
        )

        row = cursor.fetchone()
        conn.commit()

        if row:
            return row[0]

        return None

    except Exception as exc:
        conn.rollback()
        print("SERVICE CENTER ADD ANNOUNCEMENT ERROR:", exc, flush=True)
        return None

    finally:
        conn.close()


def count_announcements():
    """回傳目前啟用公告總數。"""
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM service_center_announcements
            WHERE is_active = TRUE
        """)
        row = cursor.fetchone()
        return int(row[0] or 0) if row else 0

    except Exception as exc:
        print("SERVICE CENTER COUNT ANNOUNCEMENT ERROR:", exc, flush=True)
        return 0

    finally:
        conn.close()


def list_announcements(limit=5, offset=0):
    """最新公告優先，回傳公告列表。"""
    limit = max(1, min(int(limit or 5), 10))
    offset = max(0, int(offset or 0))

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                title,
                body,
                created_at
            FROM service_center_announcements
            WHERE is_active = TRUE
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )

        rows = cursor.fetchall()
        items = []

        for row in rows:
            items.append({
                "id": row[0],
                "title": row[1] or "公告",
                "body": row[2] or "",
                "created_at": row[3],
            })

        return items

    except Exception as exc:
        print("SERVICE CENTER LIST ANNOUNCEMENT ERROR:", exc, flush=True)
        return []

    finally:
        conn.close()
