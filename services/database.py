import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]
#DB_NAME = os.path.join("/tmp", "app.db")

DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "5"))

_POOL = ThreadedConnectionPool(
    DB_POOL_MIN,
    DB_POOL_MAX,
    DATABASE_URL
)


class PooledConnection:
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._closed:
            self._pool.putconn(self._conn)
            self._closed = True

# =========================
# 取得 DB 連線
# =========================
def get_conn():

    return PooledConnection(_POOL, _POOL.getconn())

    #會消失版
    #conn = sqlite3.connect(DB_NAME)

    # 讓 row 可以用 dict 方式讀
    #conn.row_factory = sqlite3.Row

    #return conn


# =========================
# 初始化資料表（第一次用）
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
            chat_id TEXT,
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
            chat_id TEXT,
            fact TEXT
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

        conn.commit()
    finally:
        conn.close()