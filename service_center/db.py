from services.database import get_conn


# =========================
# 服務中心公告資料庫
# =========================
# - 公告獨立於主遊戲資料表
# - /start 會讀最新一則公告
# - 公告事項會依 created_at / id 倒序顯示

DEFAULT_ANNOUNCEMENT_KEY = "20260710_service_center_media_update"
DEFAULT_ANNOUNCEMENT_LABEL = "功能更新"
DEFAULT_ANNOUNCEMENT_TITLE = "服務中心與媒體輸入更新"
DEFAULT_ANNOUNCEMENT_BODY = """本次更新：
1. 新增服務中心 Telemini Wifi：可直接貼上 BotFather token，自動加入遊戲並設定 webhook。
2. 新增服務中心 Gemini API：可直接貼上 Gemini API Key，系統會寫入資料庫並清除快取。
3. 新增公告資料庫，公告事項會依最新公告優先顯示。
4. /start 會先顯示最新一則公告，再顯示服務中心主頁按鈕。
5. 媒體輸入更新：支援圖片分流、靜態貼圖理解，以及未支援媒體的防呆回覆。

隱私提醒：Bot token 與 Gemini API Key 送出後，服務中心會嘗試刪除原始訊息；請不要在群組或公開聊天室貼上金鑰。"""


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
            ann_key TEXT UNIQUE,
            label TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_service_center_announcements_active_latest
        ON service_center_announcements (is_active, created_at DESC, id DESC)
        """)

        cursor.execute(
            """
            INSERT INTO service_center_announcements (
                ann_key,
                label,
                title,
                body,
                is_active,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (ann_key)
            DO UPDATE SET
                label = EXCLUDED.label,
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
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


def get_latest_announcement():
    items = list_announcements(limit=1)
    return items[0] if items else None


def create_announcement(label, title, body, ann_key=None):
    """保留給之後管理員指令或後台使用。"""
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
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (ann_key, label, title, body),
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
