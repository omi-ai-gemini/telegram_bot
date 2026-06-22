import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
#DB_NAME = os.path.join("/tmp", "app.db")

# =========================
# 取得 DB 連線
# =========================
def get_conn():

    return psycopg2.connect(DATABASE_URL)

    #會消失版
    #conn = sqlite3.connect(DB_NAME)

    # 讓 row 可以用 dict 方式讀
    #conn.row_factory = sqlite3.Row

    #return conn

# =========================
# 更新 DB 內容
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
        """, (bot_id, token))

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_gemini_key(user_id, gemini_key):

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO user_config (user_id, gemini_key)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET gemini_key = EXCLUDED.gemini_key
        """, (user_id, gemini_key))

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            role TEXT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # =========================
        # 長期記憶
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts_memory (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,  -- private / group
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

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()