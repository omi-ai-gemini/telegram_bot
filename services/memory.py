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



def _resolve_user_id(user_id=None):
    if user_id is not None:
        return _text_id(user_id)

    try:
        from services.privacy_session import get_current_user_id
        return get_current_user_id()
    except Exception:
        return None


def _get_unlock_code_for(user_id, bot_id):
    try:
        from services.privacy_session import get_unlock_code
        return get_unlock_code(user_id, bot_id)
    except Exception:
        return None


def _decrypt_payload_row(user_id, bot_id, chat_id, data_type, record_key, encrypted_payload, unlock_code):
    import json
    from services.crypto_box import build_aad, decrypt_payload

    if isinstance(encrypted_payload, str):
        encrypted_payload = json.loads(encrypted_payload)

    aad = build_aad(user_id, bot_id, chat_id, data_type, record_key)
    return decrypt_payload(unlock_code, encrypted_payload, aad=aad)


# =========================
# 長期記憶（加密）
# =========================
def add_fact(bot_id, chat_id, scope, fact, user_id=None):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = str(scope)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_unlock_code_for(user_id, bot_id)

    if not user_id or not unlock_code:
        print("PRIVACY LOCKED add_fact skipped:", bot_id, chat_id)
        return False

    import uuid
    from services.encrypted_store import save_encrypted_payload

    save_encrypted_payload(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        data_type="facts_memory",
        unlock_code=unlock_code,
        payload={
            "fact": fact,
            "scope": scope,
        },
        record_key=f"fact_{uuid.uuid4().hex}",
    )

    return True


def get_facts(bot_id, chat_id, scope, user_id=None):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = str(scope)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_unlock_code_for(user_id, bot_id)

    if not user_id or not unlock_code:
        return []

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT record_key, encrypted_payload
            FROM encrypted_settings
            WHERE user_id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND data_type = 'facts_memory'
            ORDER BY created_at DESC
            LIMIT 300
        """, (
            user_id,
            bot_id,
            chat_id,
        ))

        rows = cursor.fetchall()
        facts = []

        for record_key, encrypted_payload in rows:
            try:
                payload = _decrypt_payload_row(
                    user_id,
                    bot_id,
                    chat_id,
                    "facts_memory",
                    record_key,
                    encrypted_payload,
                    unlock_code,
                )
            except Exception as exc:
                print("DECRYPT SKIP get_facts:", exc)
                continue

            if payload.get("scope") == scope and payload.get("fact"):
                facts.append(payload["fact"])

        return facts

    except Exception as e:
        print("DB ERROR get_facts:", e)
        raise

    finally:
        conn.close()


# =========================
# 短期記憶（加密）
# =========================
def add_chat(bot_id, chat_id, role, text, user_id=None):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_unlock_code_for(user_id, bot_id)

    if not user_id or not unlock_code:
        print("PRIVACY LOCKED add_chat skipped:", bot_id, chat_id, role)
        return False

    import uuid
    from services.encrypted_store import save_encrypted_payload

    record_key = f"chat_{uuid.uuid4().hex}"

    save_encrypted_payload(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        data_type="chat_memory",
        unlock_code=unlock_code,
        payload={
            "role": role,
            "text": text,
            "scope": scope,
        },
        record_key=record_key,
    )

    # =========================
    # encrypted sliding window
    # =========================
    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM encrypted_settings a
            WHERE a.id NOT IN (
                SELECT id FROM encrypted_settings
                WHERE user_id = %s
                  AND bot_id = %s
                  AND chat_id = %s
                  AND data_type = 'chat_memory'
                ORDER BY created_at DESC
                LIMIT 3000
            )
            AND a.user_id = %s
            AND a.bot_id = %s
            AND a.chat_id = %s
            AND a.data_type = 'chat_memory'
        """, (
            user_id,
            bot_id,
            chat_id,
            user_id,
            bot_id,
            chat_id,
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DB ERROR encrypted chat sliding window:", e)

    finally:
        conn.close()

    return True


def get_chat(bot_id, chat_id, user_id=None):

    bot_id = str(bot_id)
    chat_id = str(chat_id)
    scope = _get_scope(chat_id)
    user_id = _resolve_user_id(user_id)
    unlock_code = _get_unlock_code_for(user_id, bot_id)

    if not user_id or not unlock_code:
        return []

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT record_key, encrypted_payload
            FROM encrypted_settings
            WHERE user_id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND data_type = 'chat_memory'
            ORDER BY created_at DESC
            LIMIT 100
        """, (
            user_id,
            bot_id,
            chat_id,
        ))

        rows = cursor.fetchall()
        rows.reverse()
        history = []

        for record_key, encrypted_payload in rows:
            try:
                payload = _decrypt_payload_row(
                    user_id,
                    bot_id,
                    chat_id,
                    "chat_memory",
                    record_key,
                    encrypted_payload,
                    unlock_code,
                )
            except Exception as exc:
                print("DECRYPT SKIP get_chat:", exc)
                continue

            if payload.get("scope") != scope:
                continue

            history.append({
                "role": payload.get("role") or "user",
                "text": payload.get("text") or "",
            })

        return history

    except Exception as e:
        print("DB ERROR get_chat:", e)
        raise

    finally:
        conn.close()


def get_recent_chat(bot_id, chat_id, limit=30, user_id=None):

    history = get_chat(bot_id, chat_id, user_id=user_id)
    rows = history[-int(limit):]

    return [
        (item.get("role"), item.get("text"))
        for item in rows
    ]
