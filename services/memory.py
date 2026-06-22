from services.database import get_conn

# =========================
# 人格記憶
# =========================



# =========================
# 情緒記憶
# =========================


def _text_id(value):
    return str(value)

#RAN version
# emotion_memory = defaultdict(lambda: {
#     "mood": "neutral",      # happy/sad/angry/neutral
#     "level": 0              # -10~10
# })

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
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO emotion_memory (chat_id, mood, level)
        VALUES (%s, %s, %s)
        ON CONFLICT(chat_id)
        DO UPDATE SET
        mood=excluded.mood,
        level=excluded.level
        """,
        (
            chat_id,
            mood,
            level
        )
    )

    conn.commit()
    conn.close()

    #RAN version
    # """
    # delta:
    # + 正面情緒
    # - 負面情緒
    # """

    # emotion = emotion_memory[chat_id]

    # emotion["level"] += delta

    # #限制範圍
    # if emotion["level"] > 10:
    #     emotion["level"] = 10
    # if emotion["level"] < -10:
    #     emotion["level"] = -10
    
    # #更新mood
    # if emotion["level"] >= 5:
    #     emotion["mood"] = "happy"
    # elif emotion["level"] <= -5:
    #     emotion["mood"] = "angry"
    # else:
    #     emotion["mood"] = "neutral"

def get_emotion(chat_id):

    chat_id = _text_id(chat_id)
    
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT mood, level
        FROM emotion_memory
        WHERE chat_id=%s
        """,
        (chat_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row:

        return {
            "mood": row[0],
            "level": row[1]
        }

    return {
        "mood": "neutral",
        "level": 0
    }

    #RAN version
    #return emotion_memory[chat_id]

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

#RAN version
#facts_memory = defaultdict(list)

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

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO facts_memory
        (bot_id, chat_id, scope, fact)
        VALUES (%s, %s, %s, %s)
        """,
        (bot_id, chat_id, scope, fact)        
    )

    conn.commit()
    conn.close()

    #RAN version
    #facts_memory[chat_id].append(fact)

def get_facts(bot_id, chat_id, scope):

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fact
        FROM facts_memory
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
        ORDER BY id DESC
        """,
        (bot_id, chat_id, scope)        
    )

    rows = cursor.fetchall()

    conn.close()

    return [row[0] for row in rows]

def get_recent_chat(bot_id, chat_id, limit=30):

    chat_id = str(chat_id)
    scope = "group" if int(chat_id) < 0 else "private"

    conn = get_conn()
    cursor = conn.cursor()

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

    conn.close()

    rows.reverse()

    return rows

# =========================
# 短期記憶
# =========================

#RAN version
# chat_memory = defaultdict(lambda:                         
#                            deque(
#                                maxlen=100
#                                )
#                            )

def add_chat(bot_id, chat_id, role, text):

    chat_id = str(chat_id)
    scope = "group" if int(chat_id) < 0 else "private"

    conn = get_conn()
    cursor = conn.cursor()

    # =========================
    # 🟢 group：只寫一次（避免多 bot 重複）
    # =========================
    cursor.execute("""
        INSERT INTO chat_memory (
            bot_id,
            chat_id,
            scope,
            role,
            text
        ) VALUES (%s, %s, %s, %s, %s)
    """, (
        bot_id,
        chat_id,
        scope,
        role,
        text
    ))

    # =========================
    # sliding window（分 scope）
    # =========================
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
        bot_id, chat_id, scope,
        bot_id, chat_id, scope
    ))

    conn.commit()
    conn.close()

    #RAN version
    #chat_memory[chat_id].append({

    #    "role": role,
    #    "text": text

    #})

def get_chat(bot_id, chat_id):

    chat_id = str(chat_id)
    scope = "group" if int(chat_id) < 0 else "private"

    conn = get_conn()
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
        """, (chat_id, scope))

    # =========================
    # private → bot 專屬 memory
    # =========================
    else:
        cursor.execute("""
            SELECT role, text
            FROM chat_memory
            WHERE chat_id = %s AND scope = %s AND bot_id = %s
            ORDER BY id DESC
            LIMIT 100
        """, (chat_id, scope, bot_id))

    rows = cursor.fetchall()
    conn.close()

    rows.reverse()

    return [
        {"role": r[0], "text": r[1]}
        for r in rows
    ]

    #RAN version
    #return list(
    #    chat_memory[chat_id]
    #)