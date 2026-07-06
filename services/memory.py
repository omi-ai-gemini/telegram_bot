from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for, is_encrypted
from services.runtime_cache import get_cache, set_cache, delete_cache
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib
import re


def _text_id(value):
    return str(value)


def _get_scope(chat_id):
    chat_id = str(chat_id)
    return "group" if int(chat_id) < 0 else "private"


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _to_taipei_datetime(value):
    """把 DB created_at 轉成台灣時間。

    Supabase / Postgres 可能回傳 aware datetime，也可能因欄位型態回傳 naive datetime。
    naive 時先視為 UTC，再轉 Asia/Taipei，避免 Render 伺服器時區造成偏差。
    """
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(TAIPEI_TZ)


def _format_chat_time_label(created_at, now=None):
    """產生給 Gemini 看得懂、但不浪費 token 的時間標籤。"""
    dt = _to_taipei_datetime(created_at)

    if not dt:
        return ""

    now = now or datetime.now(TAIPEI_TZ)
    delta_seconds = int((now - dt).total_seconds())

    # DB 時間如果因時區或同步誤差略晚於現在，仍顯示今天 HH:MM。
    if delta_seconds < 0:
        delta_seconds = 0

    date_now = now.date()
    date_dt = dt.date()
    hhmm = dt.strftime("%H:%M")

    if date_dt == date_now:
        if delta_seconds < 60:
            return f"剛剛 {hhmm}"
        if delta_seconds < 60 * 60:
            return f"{max(1, delta_seconds // 60)} 分鐘前 {hhmm}"
        return f"今天 {hhmm}"

    if (date_now - date_dt).days == 1:
        return f"昨天 {hhmm}"

    return dt.strftime("%m/%d %H:%M")


def _history_item(role, value, bot_id, chat_id, scope, created_at=None):
    role = role or "user"
    aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
    text = _decrypt_safe(value, aad=aad)

    if not text:
        return None

    return {
        "role": role,
        "text": text,
        "created_at": str(created_at or ""),
        "time_label": _format_chat_time_label(created_at),
    }


def _facts_cache_prefix(bot_id, chat_id, scope):
    return ("facts", _text_id(bot_id), _text_id(chat_id), _text_id(scope))


def clear_facts_cache(bot_id, chat_id, scope=None):
    scope = _text_id(scope or _get_scope(chat_id))
    delete_cache(_facts_cache_prefix(bot_id, chat_id, scope))


def _decrypt_safe(value, aad=""):
    try:
        return decrypt_text(value, aad=aad)
    except Exception as exc:
        print("DECRYPT ERROR memory field skipped:", exc)
        return ""


# =========================
# 清除當前記憶
# 用於「記憶設定 / 清除當前記憶」
# =========================
def delete_current_memory(bot_id, chat_id, include_important=False):
    """
    清除當前聊天室記憶。

    include_important=False：
    - 保留 facts_memory，也就是「重點記憶」

    include_important=True：
    - 一併刪除 facts_memory
    """

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)
    include_important = bool(include_important)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # =========================
        # 群組記憶目前是 chat_id 共用
        # 所以群組清除時，清掉整個群組的記憶
        # =========================
        if scope == "group":

            cursor.execute("""
                DELETE FROM chat_memory
                WHERE chat_id = %s
                  AND scope = %s
            """, (
                chat_id,
                scope
            ))

            if include_important:
                cursor.execute("""
                    DELETE FROM facts_memory
                    WHERE chat_id = %s
                      AND scope = %s
                """, (
                    chat_id,
                    scope
                ))

        # =========================
        # 私聊記憶是 bot_id + chat_id 獨立
        # =========================
        else:

            cursor.execute("""
                DELETE FROM chat_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
            """, (
                bot_id,
                chat_id,
                scope
            ))

            if include_important:
                cursor.execute("""
                    DELETE FROM facts_memory
                    WHERE bot_id = %s
                      AND chat_id = %s
                      AND scope = %s
                """, (
                    bot_id,
                    chat_id,
                    scope
                ))

        # =========================
        # AI 訊息操作 / pending 狀態
        # =========================
        if scope == "group":
            cursor.execute("""
                DELETE FROM ai_message_actions
                WHERE chat_id = %s
            """, (chat_id,))

            cursor.execute("""
                DELETE FROM pending_ai_actions
                WHERE chat_id = %s
            """, (chat_id,))

            cursor.execute("""
                DELETE FROM memory_summaries
                WHERE chat_id = %s
                  AND scope = %s
            """, (chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_summary_state
                WHERE chat_id = %s
                  AND scope = %s
            """, (chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_state
                WHERE chat_id = %s
                  AND scope = %s
            """, (chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_archives
                WHERE chat_id = %s
                  AND scope = %s
            """, (chat_id, scope))

        else:
            cursor.execute("""
                DELETE FROM ai_message_actions
                WHERE bot_id = %s
                  AND chat_id = %s
            """, (bot_id, chat_id))

            cursor.execute("""
                DELETE FROM pending_ai_actions
                WHERE bot_id = %s
                  AND chat_id = %s
            """, (bot_id, chat_id))

            cursor.execute("""
                DELETE FROM memory_summaries
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
            """, (bot_id, chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_summary_state
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
            """, (bot_id, chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_state
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
            """, (bot_id, chat_id, scope))

            cursor.execute("""
                DELETE FROM memory_archives
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
            """, (bot_id, chat_id, scope))

        # =========================
        # 情緒記憶目前只有 chat_id
        # 所以直接清掉當前聊天室情緒
        # =========================
        cursor.execute("""
            DELETE FROM emotion_memory
            WHERE chat_id = %s
        """, (
            chat_id,
        ))

        conn.commit()

        print("DEBUG current memory deleted:", bot_id, chat_id, scope, "include_important=", include_important)

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_current_memory:", e)
        raise

    finally:
        conn.close()


# =========================
# 刪除某個 bot / chat 的所有記憶
# 舊函式保留，避免舊檔案 import 爆掉
# 實際邏輯直接走 delete_current_memory
# =========================
def delete_character_memory(bot_id, chat_id, include_important=False):

    delete_current_memory(bot_id, chat_id, include_important=include_important)


# =========================
# 情緒記憶
# =========================
def update_emotion(chat_id, delta):

    chat_id = _text_id(chat_id)

    emotion = get_emotion(chat_id)

    level = emotion["level"] + delta
    level = max(-10, min(10, level))

    if level >= 5:
        mood = "happy"

    elif level <= -5:
        mood = "angry"

    else:
        mood = "neutral"

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO emotion_memory (
                chat_id,
                mood,
                level
            )
            VALUES (%s, %s, %s)

            ON CONFLICT(chat_id)

            DO UPDATE SET
                mood = EXCLUDED.mood,
                level = EXCLUDED.level
        """, (
            chat_id,
            mood,
            level
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_emotion:", e)
        raise

    finally:
        conn.close()


def get_emotion(chat_id):

    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT mood, level
            FROM emotion_memory
            WHERE chat_id = %s
        """, (
            chat_id,
        ))

        row = cursor.fetchone()

        if row:
            return {
                "mood": row[0],
                "level": row[1]
            }

        return {
            "mood": "neutral",
            "level": 0
        }

    except Exception as e:
        print("DB ERROR get_emotion:", e)
        raise

    finally:
        conn.close()


def detect_emotion(text: str) -> int:
    """
    回傳情緒變化值
    """

    positive_words = ["謝謝", "讚", "好棒", "喜歡", "開心", "哈哈"]
    negative_words = ["生氣", "爛", "煩", "討厭", "難過", "氣死"]

    score = 0

    for w in positive_words:
        if w in text:
            score += 1

    for w in negative_words:
        if w in text:
            score -= 1

    return score


# =========================
# 長期記憶
# =========================
memory_triggers = [
    "記憶",
    "記住",
    "記得",
    "幫我記",
    "強化記憶"
]


# 判斷是否為記憶相關指令
def is_memory_command(text: str) -> bool:

    return any(trigger in text for trigger in memory_triggers)


def extract_memory_content(text: str) -> str:
    """
    把指令字去掉，只留要記的內容
    """

    for trigger in memory_triggers:
        text = text.replace(trigger, "")

    return text.strip()


# =========================
# 長期記憶：facts_memory.fact 存密文
# - important：重點記憶表單新增，權重最高
# - manual：舊版保留欄位，主流程已不再寫入
# =========================
def _normalize_fact_for_hash(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\-—_.,，。!！?？:：;；'\"“”‘’()（）\[\]{}<>《》]", "", text)
    return text


def _fact_hash(value):
    normalized = _normalize_fact_for_hash(value)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def add_fact(bot_id, chat_id, scope, fact, user_id=None, source_type="manual", importance=5):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope)
    source_type = _text_id(source_type or "manual")
    user_id = _text_id(user_id) if user_id is not None else ""

    fact = str(fact or "").strip()
    if not fact:
        return False

    try:
        importance = int(importance)
    except Exception:
        importance = 5

    importance = max(1, min(10, importance))
    fact_hash = _fact_hash(fact)

    aad = aad_for("facts_memory", "fact", bot_id, chat_id, scope)
    encrypted_fact = encrypt_text(fact, aad=aad)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO facts_memory (
                bot_id,
                chat_id,
                scope,
                fact,
                user_id,
                source_type,
                importance,
                fact_hash,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

            ON CONFLICT (bot_id, chat_id, scope, fact_hash)
            WHERE fact_hash IS NOT NULL
            DO UPDATE SET
                fact = EXCLUDED.fact,
                user_id = COALESCE(NULLIF(facts_memory.user_id, ''), EXCLUDED.user_id),
                source_type = EXCLUDED.source_type,
                importance = GREATEST(facts_memory.importance, EXCLUDED.importance),
                updated_at = CURRENT_TIMESTAMP
        """, (
            bot_id,
            chat_id,
            scope,
            encrypted_fact,
            user_id,
            source_type,
            importance,
            fact_hash
        ))

        conn.commit()
        clear_facts_cache(bot_id, chat_id, scope)

    except Exception as e:
        conn.rollback()
        print("DB ERROR add_fact:", e)
        raise

    finally:
        conn.close()

    return True


def add_important_fact(bot_id, chat_id, fact, scope=None, user_id=None):
    """
    重點記憶入口。
    目前表單暫不開放群組寫入，但函式保留 chat_id / scope，之後可延伸群組使用。
    """
    if scope is None:
        scope = _get_scope(chat_id)

    return add_fact(
        bot_id=bot_id,
        chat_id=chat_id,
        scope=scope,
        fact=fact,
        user_id=user_id,
        source_type="important",
        importance=10
    )


def get_facts(bot_id, chat_id, scope, user_id=None, limit=20, source_types=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope)

    if source_types is None:
        # 手動記憶已由「重點記憶」取代。
        # 預設只讀重點記憶，避免舊版 manual 資料繼續進 prompt。
        source_types = ["important"]

    limit = max(1, min(int(limit or 20), 50))
    cache_key = _facts_cache_prefix(bot_id, chat_id, scope) + (
        _text_id(user_id or ""),
        limit,
        tuple(source_types),
    )

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fact, source_type, importance
            FROM facts_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND source_type = ANY(%s)
            ORDER BY
                importance DESC,
                CASE WHEN source_type = 'important' THEN 0 ELSE 1 END,
                updated_at DESC,
                created_at DESC
            LIMIT %s
        """, (
            bot_id,
            chat_id,
            scope,
            source_types,
            limit
        ))

        rows = cursor.fetchall()
        aad = aad_for("facts_memory", "fact", bot_id, chat_id, scope)

        facts = []

        for row in rows:
            fact = _decrypt_safe(row[0], aad=aad)
            if fact:
                facts.append(fact)

        return set_cache(cache_key, facts, ttl=30)

    except Exception as e:
        print("DB ERROR get_facts:", e)
        raise

    finally:
        conn.close()



# =========================
# 重點記憶管理：列表 / 修改 / 單筆刪除
# =========================
def _user_filter_sql(user_id, params):
    """
    舊資料沒有 user_id，所以管理頁允許看到 user_id 空白的既有重點記憶。
    新資料會寫入 user_id，之後可再收斂成嚴格權限。
    """
    user_id = str(user_id or "").strip()

    if not user_id:
        return "", params

    params.append(user_id)
    return " AND (user_id = %s OR user_id IS NULL OR user_id = '')", params


def list_important_facts(bot_id, chat_id, scope=None, user_id=None, limit=100):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))

    try:
        limit = int(limit or 100)
    except Exception:
        limit = 100

    limit = max(1, min(limit, 100))

    conn = get_conn()

    try:
        cursor = conn.cursor()

        params = [bot_id, chat_id, scope]
        user_sql, params = _user_filter_sql(user_id, params)
        params.append(limit)

        cursor.execute(f"""
            SELECT id, fact, created_at, updated_at
            FROM facts_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND source_type = 'important'
              {user_sql}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT %s
        """, params)

        rows = cursor.fetchall()
        aad = aad_for("facts_memory", "fact", bot_id, chat_id, scope)
        facts = []

        for row_id, value, created_at, updated_at in rows:
            fact = _decrypt_safe(value, aad=aad)
            if not fact:
                continue

            facts.append({
                "id": row_id,
                "fact": fact,
                "created_at": str(created_at or ""),
                "updated_at": str(updated_at or "")
            })

        return facts

    except Exception as e:
        print("DB ERROR list_important_facts:", e)
        raise

    finally:
        conn.close()


def update_important_fact(memory_id, bot_id, chat_id, fact, scope=None, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))
    user_id = _text_id(user_id) if user_id is not None else ""

    try:
        memory_id = int(memory_id)
    except Exception:
        return False, "memory_id 格式錯誤。"

    fact = str(fact or "").strip()
    if not fact:
        return False, "重點記憶不能空白。"

    fact_hash = _fact_hash(fact)
    aad = aad_for("facts_memory", "fact", bot_id, chat_id, scope)
    encrypted_fact = encrypt_text(fact, aad=aad)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        params = [bot_id, chat_id, scope, fact_hash, memory_id]
        user_sql, params = _user_filter_sql(user_id, params)

        cursor.execute(f"""
            SELECT id
            FROM facts_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND source_type = 'important'
              AND fact_hash = %s
              AND id <> %s
              {user_sql}
            LIMIT 1
        """, params)

        if cursor.fetchone():
            return False, "已經有相同的重點記憶。"

        params = [encrypted_fact, fact_hash, user_id, memory_id, bot_id, chat_id, scope]
        user_sql, params = _user_filter_sql(user_id, params)

        cursor.execute(f"""
            UPDATE facts_memory
            SET fact = %s,
                fact_hash = %s,
                user_id = COALESCE(NULLIF(user_id, ''), %s),
                source_type = 'important',
                importance = 10,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND source_type = 'important'
              {user_sql}
        """, params)

        if cursor.rowcount == 0:
            conn.rollback()
            return False, "找不到這筆重點記憶，或沒有可修改的資料。"

        conn.commit()
        clear_facts_cache(bot_id, chat_id, scope)
        return True, "重點記憶已修改。"

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_important_fact:", e)
        return False, "修改失敗，請稍後再試。"

    finally:
        conn.close()


def delete_important_fact(memory_id, bot_id, chat_id, scope=None, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))

    try:
        memory_id = int(memory_id)
    except Exception:
        return False, "memory_id 格式錯誤。"

    conn = get_conn()

    try:
        cursor = conn.cursor()

        params = [memory_id, bot_id, chat_id, scope]
        user_sql, params = _user_filter_sql(user_id, params)

        cursor.execute(f"""
            DELETE FROM facts_memory
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND source_type = 'important'
              {user_sql}
        """, params)

        if cursor.rowcount == 0:
            conn.rollback()
            return False, "找不到這筆重點記憶，或已經被刪除。"

        conn.commit()
        clear_facts_cache(bot_id, chat_id, scope)
        return True, "重點記憶已刪除。"

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_important_fact:", e)
        return False, "刪除失敗，請稍後再試。"

    finally:
        conn.close()


# =========================
# 短期記憶：chat_memory.text 存密文
# =========================
def add_chat(bot_id, chat_id, role, text, user_id=None, telegram_message_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)
    role = _text_id(role)
    user_id = None if user_id is None else _text_id(user_id)

    aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
    encrypted_text = encrypt_text(text, aad=aad)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO chat_memory (
                bot_id,
                chat_id,
                scope,
                role,
                text,
                user_id,
                telegram_message_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            bot_id,
            chat_id,
            scope,
            role,
            encrypted_text,
            user_id,
            telegram_message_id
        ))

        row = cursor.fetchone()
        memory_id = int(row[0]) if row else None

        # 注意：不要在這裡直接刪掉超過 100 則的舊短期記憶。
        # 舊訊息必須先被 memory_summary 摘要成功，才可以被清理。

        conn.commit()
        return memory_id

    except Exception as e:
        conn.rollback()
        print("DB ERROR add_chat:", e)
        raise

    finally:
        conn.close()


def update_chat_text(memory_id, bot_id, chat_id, role, text):
    """更新既有 chat_memory 文字，用於手動修改 / 重跑 AI 回覆。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)
    role = _text_id(role or "assistant")

    try:
        memory_id = int(memory_id)
    except Exception:
        return False

    aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
    encrypted_text = encrypt_text(text, aad=aad)

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE chat_memory
            SET text = %s
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND role = %s
        """, (
            encrypted_text,
            memory_id,
            bot_id,
            chat_id,
            scope,
            role
        ))

        ok = cursor.rowcount > 0
        conn.commit()
        return ok

    except Exception as e:
        conn.rollback()
        print("DB ERROR update_chat_text:", e)
        return False

    finally:
        conn.close()


def get_chat_memory_item(memory_id, bot_id, chat_id):
    """取得單筆 chat_memory，並自動解密 text。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    try:
        memory_id = int(memory_id)
    except Exception:
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, role, text, user_id, telegram_message_id
            FROM chat_memory
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
        """, (memory_id, bot_id, chat_id, scope))

        row = cursor.fetchone()
        if not row:
            return None

        row_id, role, value, row_user_id, telegram_message_id = row
        role = role or "user"
        aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
        text = _decrypt_safe(value, aad=aad)

        return {
            "id": row_id,
            "role": role,
            "text": text,
            "user_id": row_user_id,
            "telegram_message_id": telegram_message_id,
        }

    except Exception as e:
        print("DB ERROR get_chat_memory_item:", e)
        return None

    finally:
        conn.close()


def get_chat_until(bot_id, chat_id, max_chat_id, user_id=None):
    """取得指定 chat_memory id 以前的對話，用於重跑 / 接續。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    try:
        max_chat_id = int(max_chat_id)
    except Exception:
        return []

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, text, created_at
            FROM chat_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND id <= %s
            ORDER BY id ASC
        """, (bot_id, chat_id, scope, max_chat_id))

        rows = cursor.fetchall()
        history = []

        for role, value, created_at in rows:
            item = _history_item(role, value, bot_id, chat_id, scope, created_at=created_at)
            if item:
                history.append(item)

        return history

    except Exception as e:
        print("DB ERROR get_chat_until:", e)
        return []

    finally:
        conn.close()


def get_chat(bot_id, chat_id, user_id=None):

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT role, text, created_at
            FROM chat_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id ASC
        """, (
            bot_id,
            chat_id,
            scope
        ))

        rows = cursor.fetchall()
        history = []

        for role, value, created_at in rows:
            item = _history_item(role, value, bot_id, chat_id, scope, created_at=created_at)
            if item:
                history.append(item)

        return history

    except Exception as e:
        print("DB ERROR get_chat:", e)
        raise

    finally:
        conn.close()


def get_chat_for_prompt(bot_id, chat_id, user_id=None, mode="聊天模式"):
    """取得要送進 Gemini 的近期對話，並加上時間標籤。

    設計：
    - 聊天模式：保留 60 分鐘內最多 60 則，外加更早的 20 則補上下文。
    - 劇場模式：保留 180 分鐘內最多 80 則，外加更早的 30 則補場景。
    - 不改 DB，只使用 chat_memory.created_at。
    """
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)
    mode = str(mode or "聊天模式")

    if mode == "劇場模式":
        window_minutes = 180
        max_window_rows = 80
        fallback_rows = 30
    else:
        window_minutes = 60
        max_window_rows = 60
        fallback_rows = 20

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, role, text, created_at
            FROM chat_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id ASC
        """, (bot_id, chat_id, scope))

        rows = cursor.fetchall()
        now = datetime.now(TAIPEI_TZ)
        window_seconds = window_minutes * 60

        parsed = []
        for row_id, role, value, created_at in rows:
            item = _history_item(role, value, bot_id, chat_id, scope, created_at=created_at)
            if not item:
                continue

            dt = _to_taipei_datetime(created_at)
            age_seconds = None
            if dt:
                age_seconds = int((now - dt).total_seconds())

            item["id"] = int(row_id)
            item["age_seconds"] = age_seconds
            parsed.append(item)

        if not parsed:
            return []

        in_window = [
            item for item in parsed
            if item.get("age_seconds") is not None
            and item.get("age_seconds") >= 0
            and item.get("age_seconds") <= window_seconds
        ]

        if not in_window:
            selected = parsed[-max_window_rows:]
        else:
            in_window = in_window[-max_window_rows:]
            first_window_id = in_window[0]["id"]
            older = [item for item in parsed if item["id"] < first_window_id]
            selected = older[-fallback_rows:] + in_window

        # 去重並保留時間順序。
        seen = set()
        result = []
        for item in selected:
            item_id = item.get("id")
            if item_id in seen:
                continue
            seen.add(item_id)
            item.pop("age_seconds", None)
            result.append(item)

        print(
            f"[MEMORY TIME] mode={mode} window_minutes={window_minutes} "
            f"rows={len(result)} total={len(parsed)} scope={scope}",
            flush=True,
        )

        return result

    except Exception as e:
        print("DB ERROR get_chat_for_prompt:", e)
        raise

    finally:
        conn.close()


def list_recent_chat_memory(bot_id, chat_id, limit=10, user_id=None):
    """列出最近 N 筆短期記憶，含 id，給 /memory 查看與單筆刪除使用。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    try:
        limit = int(limit or 10)
    except Exception:
        limit = 10

    limit = max(1, min(limit, 30))

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, role, text, user_id, telegram_message_id, created_at
            FROM chat_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id DESC
            LIMIT %s
        """, (bot_id, chat_id, scope, limit))

        rows = cursor.fetchall()
        result = []

        for row_id, role, value, row_user_id, telegram_message_id, created_at in rows:
            role = role or "user"
            aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
            text = _decrypt_safe(value, aad=aad)

            if not text:
                continue

            result.append({
                "id": int(row_id),
                "role": role,
                "text": text,
                "user_id": row_user_id,
                "telegram_message_id": telegram_message_id,
                "created_at": str(created_at or ""),
            })

        return result

    except Exception as e:
        print("DB ERROR list_recent_chat_memory:", e)
        return []

    finally:
        conn.close()


def delete_chat_memory_item(memory_id, bot_id, chat_id):
    """刪除單筆短期記憶，並清掉跟該筆記憶綁定的 AI 操作映射。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    try:
        memory_id = int(memory_id)
    except Exception:
        return False, "memory_id 格式錯誤"

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM ai_message_actions
            WHERE bot_id = %s
              AND chat_id = %s
              AND (
                    assistant_chat_id = %s
                 OR source_user_chat_id = %s
                 OR context_chat_id = %s
              )
        """, (bot_id, chat_id, memory_id, memory_id, memory_id))

        cursor.execute("""
            DELETE FROM chat_memory
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
        """, (memory_id, bot_id, chat_id, scope))

        if cursor.rowcount == 0:
            conn.rollback()
            return False, "找不到這筆短期記憶"

        conn.commit()
        return True, "已刪除短期記憶"

    except Exception as e:
        conn.rollback()
        print("DB ERROR delete_chat_memory_item:", e)
        return False, "刪除短期記憶失敗"

    finally:
        conn.close()


def get_recent_chat(bot_id, chat_id, limit=30, user_id=None):

    history = get_chat(bot_id, chat_id, user_id=user_id)
    rows = history[-int(limit):]

    return [
        (item.get("role"), item.get("text"))
        for item in rows
    ]
