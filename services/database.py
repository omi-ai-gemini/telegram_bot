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
# 初始化資料表（第一次用）
# =========================
def init_db():

    conn = get_conn()
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
    conn.close()