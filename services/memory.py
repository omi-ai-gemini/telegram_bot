from services.database import get_conn


def _text_id(value):
    return str(value)


def _get_scope(chat_id):
    chat_id = str(chat_id)
    return "group" if int(chat_id) < 0 else "private"


# =========================
# 清除當前記憶
# 用於「記憶設定 / 清除當前記憶」
# =========================
def delete_current_memory(bot_id, chat_id):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)

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

        print("DEBUG current memory deleted:", bot_id, chat_id, scope)

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
def delete_character_memory(bot_id, chat_id):

    delete_current_memory(bot_id, chat_id)


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


def add_fact(bot_id, chat_id, scope, fact):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = str(scope)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO facts_memory (
                bot_id,
                chat_id,
                scope,
                fact
            )
            VALUES (%s, %s, %s, %s)
        """, (
            bot_id,
            chat_id,
            scope,
            fact
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DB ERROR add_fact:", e)
        raise

    finally:
        conn.close()


def get_facts(bot_id, chat_id, scope):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = str(scope)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fact
            FROM facts_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id DESC
        """, (
            bot_id,
            chat_id,
            scope
        ))

        rows = cursor.fetchall()

        return [row[0] for row in rows]

    except Exception as e:
        print("DB ERROR get_facts:", e)
        raise

    finally:
        conn.close()


# =========================
# 短期記憶
# =========================
def add_chat(bot_id, chat_id, role, text):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO chat_memory (
                bot_id,
                chat_id,
                scope,
                role,
                text
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            bot_id,
            chat_id,
            scope,
            role,
            text
        ))

        # =========================
        # sliding window
        # 私聊：bot_id + chat_id + scope 保留 3000 筆
        # 群組：chat_id + scope 共用保留 3000 筆
        # =========================
        if scope == "group":

            cursor.execute("""
                DELETE FROM chat_memory a
                WHERE a.id NOT IN (
                    SELECT id FROM chat_memory
                    WHERE chat_id = %s
                      AND scope = %s
                    ORDER BY id DESC
                    LIMIT 3000
                )
                AND a.chat_id = %s
                AND a.scope = %s
            """, (
                chat_id,
                scope,
                chat_id,
                scope
            ))

        else:

            cursor.execute("""
                DELETE FROM chat_memory a
                WHERE a.id NOT IN (
                    SELECT id FROM chat_memory
                    WHERE bot_id = %s
                      AND chat_id = %s
                      AND scope = %s
                    ORDER BY id DESC
                    LIMIT 3000
                )
                AND a.bot_id = %s
                AND a.chat_id = %s
                AND a.scope = %s
            """, (
                bot_id,
                chat_id,
                scope,
                bot_id,
                chat_id,
                scope
            ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DB ERROR add_chat:", e)
        raise

    finally:
        conn.close()


def get_chat(bot_id, chat_id):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # =========================
        # group → 共用 memory
        # =========================
        if scope == "group":

            cursor.execute("""
                SELECT role, text
                FROM chat_memory
                WHERE chat_id = %s 
                  AND scope = %s
                ORDER BY id DESC
                LIMIT 100
            """, (
                chat_id,
                scope
            ))

        # =========================
        # private → bot 專屬 memory
        # =========================
        else:

            cursor.execute("""
                SELECT role, text
                FROM chat_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
                ORDER BY id DESC
                LIMIT 100
            """, (
                bot_id,
                chat_id,
                scope
            ))

        rows = cursor.fetchall()
        rows.reverse()

        return [
            {
                "role": r[0],
                "text": r[1]
            }
            for r in rows
        ]

    except Exception as e:
        print("DB ERROR get_chat:", e)
        raise

    finally:
        conn.close()


def get_recent_chat(bot_id, chat_id, limit=30):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # =========================
        # group → 共用 memory
        # =========================
        if scope == "group":

            cursor.execute("""
                SELECT role, text
                FROM chat_memory
                WHERE chat_id = %s
                  AND scope = %s
                ORDER BY id DESC
                LIMIT %s
            """, (
                chat_id,
                scope,
                limit
            ))

        # =========================
        # private → bot 專屬 memory
        # =========================
        else:

            cursor.execute("""
                SELECT role, text
                FROM chat_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
                ORDER BY id DESC
                LIMIT %s
            """, (
                bot_id,
                chat_id,
                scope,
                limit
            ))

        rows = cursor.fetchall()
        rows.reverse()

        return rows

    except Exception as e:
        print("DB ERROR get_recent_chat:", e)
        raise

    finally:
        conn.close()