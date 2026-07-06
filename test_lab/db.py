from services.database import get_conn


# =========================
# Test Lab / Prompt Tuner 資料表
# =========================
# 表名全部以 test_ 開頭，避免和主遊戲資料表混用。

def init_test_lab_db():
    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_profiles (
            bot_id TEXT NOT NULL,
            real_user_id TEXT NOT NULL,
            test_user_id TEXT NOT NULL,
            gemini_api_key TEXT,
            model TEXT NOT NULL DEFAULT 'gemini-3.1-flash-lite',
            temperature NUMERIC NOT NULL DEFAULT 0.7,
            max_output_tokens INTEGER NOT NULL DEFAULT 768,
            lab_goal TEXT,
            base_style TEXT,
            response_rules TEXT,
            reference_style TEXT,
            current_prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (bot_id, real_user_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_profiles_test_user
        ON test_profiles (bot_id, test_user_id)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_sessions (
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            real_user_id TEXT NOT NULL,
            test_user_id TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            awaiting_api_key BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (bot_id, chat_id, real_user_id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_sessions_active
        ON test_sessions (bot_id, chat_id, real_user_id, is_active)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_memory (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            real_user_id TEXT NOT NULL,
            test_user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_memory_lookup
        ON test_memory (bot_id, chat_id, test_user_id, id DESC)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_summaries (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            real_user_id TEXT NOT NULL,
            test_user_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            source_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_summaries_lookup
        ON test_summaries (bot_id, chat_id, test_user_id, id DESC)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_prompt_versions (
            id SERIAL PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            real_user_id TEXT NOT NULL,
            test_user_id TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            source_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_prompt_versions_lookup
        ON test_prompt_versions (bot_id, chat_id, test_user_id, id DESC)
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
