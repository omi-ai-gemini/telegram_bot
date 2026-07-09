import os
import psycopg2
import threading
import time
from services.runtime_cache import delete_cache
from services.crypto_env import encrypt_text, aad_for

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




def _encrypt_db_secret_safe(value, aad=""):
    """敏感金鑰入 DB 前加密；若環境密鑰異常則保底不讓流程中斷。"""
    try:
        return encrypt_text(value, aad=aad)
    except Exception as exc:
        print("DB SECRET ENCRYPT SKIPPED:", exc, flush=True)
        return value

# =========================
# 更新 bot token
# =========================
def save_bot(bot_id, token):

    bot_id = str(bot_id)
    encrypted_token = _encrypt_db_secret_safe(
        token,
        aad=aad_for("bot_config", "token", bot_id),
    )

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
            encrypted_token
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

    user_id = str(user_id)
    encrypted_key = _encrypt_db_secret_safe(
        gemini_key,
        aad=aad_for("user_config", "gemini_key", user_id),
    )

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
            encrypted_key
        ))

        conn.commit()
        delete_cache(("gemini_key", str(user_id)))

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
            user_id TEXT,
            telegram_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        ALTER TABLE chat_memory
        ADD COLUMN IF NOT EXISTS user_id TEXT
        """)

        cursor.execute("""
        ALTER TABLE chat_memory
        ADD COLUMN IF NOT EXISTS telegram_message_id INTEGER
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_memory_lookup
        ON chat_memory (bot_id, chat_id, scope, id)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_memory_telegram_message
        ON chat_memory (bot_id, chat_id, telegram_message_id)
        """)

        # =========================
        # AI 訊息操作映射
        # 用於每則 AI 訊息下方的：修改 / 重跑 / 接續
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_message_actions (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            user_id TEXT,
            telegram_message_id INTEGER,
            assistant_chat_id INTEGER NOT NULL,
            source_user_chat_id INTEGER,
            context_chat_id INTEGER,
            generation_type TEXT DEFAULT 'reply',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        ALTER TABLE ai_message_actions
        ADD COLUMN IF NOT EXISTS source_user_chat_id INTEGER
        """)

        cursor.execute("""
        ALTER TABLE ai_message_actions
        ADD COLUMN IF NOT EXISTS context_chat_id INTEGER
        """)

        cursor.execute("""
        ALTER TABLE ai_message_actions
        ADD COLUMN IF NOT EXISTS generation_type TEXT DEFAULT 'reply'
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_message_actions_lookup
        ON ai_message_actions (bot_id, chat_id, user_id, id)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_message_actions_message
        ON ai_message_actions (bot_id, chat_id, telegram_message_id)
        """)

        # =========================
        # 等待使用者下一句文字的操作
        # 例如：按下「改」後，下一句文字只拿來覆蓋 AI 訊息，不進記憶。
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_ai_actions (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_action_id INTEGER NOT NULL,
            prompt_message_id INTEGER,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_ai_actions_lookup
        ON pending_ai_actions (bot_id, chat_id, user_id, action_type, expires_at)
        """)

        # =========================
        # 設定選單 session
        # 用於按「結束設定」時，同時刪除使用者輸入的 /setting 或 /設定。
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS setting_menu_sessions (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            user_id TEXT,
            menu_message_id INTEGER NOT NULL,
            command_message_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (bot_id, chat_id, menu_message_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_setting_menu_sessions_lookup
        ON setting_menu_sessions (bot_id, chat_id, menu_message_id)
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

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_memory_lookup
        ON facts_memory (bot_id, chat_id, scope, created_at)
        """)

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'manual'
        """)

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS importance INTEGER DEFAULT 5
        """)

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS fact_hash TEXT
        """)

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cursor.execute("""
        ALTER TABLE facts_memory
        ADD COLUMN IF NOT EXISTS user_id TEXT
        """)

        cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_memory_unique_hash
        ON facts_memory (bot_id, chat_id, scope, fact_hash)
        WHERE fact_hash IS NOT NULL
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_memory_priority
        ON facts_memory (bot_id, chat_id, scope, source_type, importance, updated_at)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_memory_user_lookup
        ON facts_memory (bot_id, chat_id, scope, user_id, source_type, updated_at)
        """)

        # =========================
        # 摘要型長期記憶：摘要進度
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_summary_state (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            last_summarized_chat_id INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id, scope)
        )
        """)

        # =========================
        # 摘要型長期記憶：每 50 則短期訊息一段
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_summaries (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            start_chat_id INTEGER NOT NULL,
            end_chat_id INTEGER NOT NULL,
            summary TEXT NOT NULL,
            summary_type TEXT DEFAULT 'segment',
            is_archived BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (bot_id, chat_id, scope, start_chat_id, end_chat_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_summaries_lookup
        ON memory_summaries (bot_id, chat_id, scope, is_archived, start_chat_id)
        """)

        # =========================
        # 摘要型長期記憶：目前狀態
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_state (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id, scope)
        )
        """)

        # =========================
        # 摘要型長期記憶：舊摘要封存
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_archives (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            start_summary_id INTEGER,
            end_summary_id INTEGER,
            archive_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_archives_lookup
        ON memory_archives (bot_id, chat_id, scope, id)
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
        # reply_style 保留舊欄位相容性，但新流程不再把風格存在這張表
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
            reply_style TEXT DEFAULT '',

            user_gender TEXT DEFAULT '',
            user_appearance TEXT DEFAULT '',
            user_other_settings TEXT DEFAULT '',

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id)
        )
        """)

        cursor.execute("""
        ALTER TABLE character_settings
        ADD COLUMN IF NOT EXISTS reply_style TEXT DEFAULT ''
        """)

        cursor.execute("""
        ALTER TABLE character_settings
        ADD COLUMN IF NOT EXISTS opening_sent BOOLEAN DEFAULT FALSE
        """)

        cursor.execute("""
        ALTER TABLE character_settings
        ADD COLUMN IF NOT EXISTS script_hash TEXT DEFAULT ''
        """)

        # =========================
        # 聊天模式人物設定
        # reply_style 保留舊欄位相容性，但新流程不再把風格存在這張表
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_persona_settings (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,

            persona_name TEXT DEFAULT '',
            persona_gender TEXT DEFAULT '',
            persona_background TEXT DEFAULT '',
            reply_style TEXT DEFAULT '',

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id)
        )
        """)

        cursor.execute("""
        ALTER TABLE chat_persona_settings
        ADD COLUMN IF NOT EXISTS reply_style TEXT DEFAULT ''
        """)

        # =========================
        # 回覆風格設定
        # 與人物 / 劇本分離，換人物或換劇本時風格仍可保留
        # style_type：chat / theater
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reply_style_settings (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            style_type TEXT NOT NULL,
            reply_style TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (bot_id, chat_id, style_type)
        )
        """)


        # =========================
        # 通用加密資料表
        # 使用者解鎖碼不存 DB；只存加密後的 JSONB payload
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS encrypted_settings (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            data_type TEXT NOT NULL,
            record_key TEXT NOT NULL DEFAULT 'default',
            encrypted_payload JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (user_id, bot_id, chat_id, data_type, record_key)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_encrypted_settings_lookup
        ON encrypted_settings (user_id, bot_id, chat_id, data_type)
        """)

        # =========================
        # 隱私管理權限
        # 只記錄使用者是否已取得資料庫密碼，不保存密碼明文
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS privacy_access (
            user_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            unlock_code_issued BOOLEAN NOT NULL DEFAULT FALSE,
            delivery_status TEXT NOT NULL DEFAULT 'not_issued',
            issued_chat_id TEXT,
            issued_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (user_id, bot_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_privacy_access_lookup
        ON privacy_access (bot_id, user_id, unlock_code_issued)
        """)

        # =========================
        # 一次性使用者公告紀錄
        # 每個 user + bot + notice_id 只發一次
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_notice_log (
            user_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            notice_id TEXT NOT NULL,
            delivered_chat_id TEXT,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (user_id, bot_id, notice_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_notice_log_lookup
        ON user_notice_log (bot_id, notice_id, user_id)
        """)

        # =========================
        # Prompt Debug 紀錄
        # 開發者用：保存每次主遊戲送進 Gemini 的完整 prompt，改由網頁查看。
        # =========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_debug_logs (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            source TEXT DEFAULT 'unknown',
            generation_type TEXT DEFAULT 'unknown',
            action_id INTEGER,
            source_user_chat_id INTEGER,
            model TEXT,
            prompt_text TEXT NOT NULL,
            prompt_chars INTEGER DEFAULT 0,
            prompt_hash TEXT,
            status TEXT DEFAULT 'built',
            finish_reason TEXT,
            block_reason TEXT,
            response_chars INTEGER,
            prompt_meta JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # =========================
        # 舊版 prompt_debug_logs 相容補欄位
        # 注意：CREATE TABLE IF NOT EXISTS 不會幫既有資料表補新欄位。
        # 若手機救火版已建立舊表，這裡必須先 ALTER，再建立索引，
        # 否則會因 action_id / user_id 等欄位不存在造成整個 Flask before_request 500。
        # =========================
        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS user_id TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'unknown'
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS generation_type TEXT DEFAULT 'unknown'
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS action_id INTEGER
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS source_user_chat_id INTEGER
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS model TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS prompt_text TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS prompt_chars INTEGER DEFAULT 0
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS prompt_hash TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'built'
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS finish_reason TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS block_reason TEXT
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS response_chars INTEGER
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS prompt_meta JSONB DEFAULT '{}'::jsonb
        """)

        cursor.execute("""
        ALTER TABLE prompt_debug_logs
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_debug_logs_lookup
        ON prompt_debug_logs (bot_id, chat_id, user_id, id DESC)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_debug_logs_action
        ON prompt_debug_logs (bot_id, chat_id, action_id)
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
