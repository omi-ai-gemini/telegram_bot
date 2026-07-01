import os
import psycopg2
import threading
import time

DATABASE_URL = os.environ["DATABASE_URL"]

# =========================
# DB 連線監控
# =========================
_DB_LOCK = threading.Lock()
_ACTIVE_DB_CONNECTIONS = 0
_TOTAL_DB_CONNECTIONS = 0


# =========================
# DB 連線包裝器
# 用來統計目前同時開啟幾條 DB 連線
# =========================
class TrackedConnection:

    def __init__(self, conn, conn_id):
        self._conn = conn
        self._conn_id = conn_id
        self._closed = False

    def close(self):
        global _ACTIVE_DB_CONNECTIONS

        if self._closed:
            return

        try:
            self._conn.close()

        finally:
            self._closed = True

            with _DB_LOCK:
                _ACTIVE_DB_CONNECTIONS -= 1

                if _ACTIVE_DB_CONNECTIONS < 0:
                    _ACTIVE_DB_CONNECTIONS = 0

                print(
                    f"[DB CLOSE] id={self._conn_id} "
                    f"active={_ACTIVE_DB_CONNECTIONS}",
                    flush=True
                )

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


# =========================
# 取得 DB 連線
# =========================
def get_conn():

    global _ACTIVE_DB_CONNECTIONS
    global _TOTAL_DB_CONNECTIONS

    conn = psycopg2.connect(DATABASE_URL)

    with _DB_LOCK:
        _ACTIVE_DB_CONNECTIONS += 1
        _TOTAL_DB_CONNECTIONS += 1

        conn_id = _TOTAL_DB_CONNECTIONS

        print(
            f"[DB OPEN] id={conn_id} "
            f"active={_ACTIVE_DB_CONNECTIONS} "
            f"pid={os.getpid()} "
            f"time={time.strftime('%Y-%m-%d %H:%M:%S')}",
            flush=True
        )

    return TrackedConnection(conn, conn_id)


# =========================
# 取得目前 DB 連線統計
# =========================
def get_db_connection_stats():

    with _DB_LOCK:
        return {
            "active": _ACTIVE_DB_CONNECTIONS,
            "total_opened": _TOTAL_DB_CONNECTIONS,
            "pid": os.getpid()
        }


# =========================
# 更新 bot token
# =========================
def save_bot(bot_id, token):

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO bot_config (bot_id, token)
        VALUES (%s, %s)
        ON CONFLICT (bot_id)
        DO UPDATE SET token = EXCLUDED.token
        """, (
            bot_id,
            token
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =========================
# 更新 Gemini API key
# =========================
def update_gemini_key(user_id, gemini_key):

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO user_config (user_id, gemini_key)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET gemini_key = EXCLUDED.gemini_key
        """, (
            user_id,
            gemini_key
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =========================
# 初始化資料表
# =========================
def init_db():

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # =========================
        # bot token table
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            bot_id TEXT PRIMARY KEY,
            token TEXT NOT NULL
        )
        """)

        # =========================
        # user gemini key table
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_config (
            user_id TEXT PRIMARY KEY,
            gemini_key TEXT
        )
        """)

        # =========================
        # 短期記憶
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_memory (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            role TEXT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # =========================
        # 長期記憶
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts_memory (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # =========================
        # 情緒記憶
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emotion_memory (
            chat_id TEXT PRIMARY KEY,
            mood TEXT,
            level INTEGER
        )
        """)

        # =========================
        # 劇本模式設定
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_settings (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,

            mode TEXT NOT NULL DEFAULT '聊天模式',

            ai_name TEXT DEFAULT '',
            ai_gender TEXT DEFAULT '',
            ai_appearance TEXT DEFAULT '',
            story_background TEXT DEFAULT '',
            ai_opening TEXT DEFAULT '',

            user_gender TEXT DEFAULT '',
            user_appearance TEXT DEFAULT '',
            user_other_settings TEXT DEFAULT '',

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id)
        )
        """)

        # =========================
        # 聊天模式人物設定
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_persona_settings (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,

            persona_name TEXT DEFAULT '',
            persona_gender TEXT DEFAULT '',
            persona_background TEXT DEFAULT '',

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id)
        )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
