from services.database import get_conn


# =========================
# 人格記憶
# =========================
PERSONA_SETTING_COMMAND = "//設定"

PERSONA_FIELDS = [
    ("模式設定(陪伴模式C/劇場模式T)", "mode_setting"),
    ("AI暱稱", "ai_nickname"),
    ("AI外觀", "ai_appearance"),
    ("AI背景", "ai_background"),
    ("AI回覆風格", "ai_reply_style"),
    ("User暱稱", "user_nickname"),
    ("User外觀", "user_appearance"),
    ("User背景", "user_background"),
]

PERSONA_FIELD_LABELS = [label for label, _ in PERSONA_FIELDS]
PERSONA_FIELD_MAP = dict(PERSONA_FIELDS)


def ensure_persona_memory(chat_id):
    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO persona_memory (
            chat_id,
            mode_setting,
            ai_nickname,
            ai_appearance,
            ai_background,
            ai_reply_style,
            user_nickname,
            user_appearance,
            user_background
        )
        VALUES (%s, '', '', '', '', '', '', '', '')
        ON CONFLICT (chat_id) DO NOTHING
        """,
        (chat_id,)
    )

    conn.commit()
    conn.close()


def get_persona_settings(chat_id):
    chat_id = _text_id(chat_id)
    ensure_persona_memory(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            mode_setting,
            ai_nickname,
            ai_appearance,
            ai_background,
            ai_reply_style,
            user_nickname,
            user_appearance,
            user_background
        FROM persona_memory
        WHERE chat_id = %s
        """,
        (chat_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {label: "" for label in PERSONA_FIELD_LABELS}

    return {
        label: row[index] or ""
        for index, (label, _) in enumerate(PERSONA_FIELDS)
    }


def build_persona_form(chat_id):
    settings = get_persona_settings(chat_id)
    lines = [PERSONA_SETTING_COMMAND]

    for label in PERSONA_FIELD_LABELS:
        lines.append(f"{label}:{settings.get(label, '')}")

    return "\n".join(lines)


def _split_persona_line(line):
    half_index = line.find(":")
    full_index = line.find("：")
    indexes = [index for index in [half_index, full_index] if index != -1]

    if not indexes:
        return None

    separator_index = min(indexes)
    key = line[:separator_index].strip()
    value = line[separator_index + 1:].strip()

    return key, value


def parse_persona_form(text):
    lines = [
        line.strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]

    if not lines or lines[0] != PERSONA_SETTING_COMMAND:
        return None, "設定表單必須以 //設定 開頭。"

    values = {}

    for line in lines[1:]:
        parsed = _split_persona_line(line)

        if not parsed:
            return None, f"設定格式錯誤：{line}"

        key, value = parsed

        if key not in PERSONA_FIELD_MAP:
            return None, f"設定欄位被修改或不存在：{key}"

        if key in values:
            return None, f"設定欄位重複：{key}"

        values[key] = value

    missing = [label for label in PERSONA_FIELD_LABELS if label not in values]

    if missing:
        return None, "設定表單已被修改，請重新輸入 //設定 取得最新表單。\n缺少欄位：" + "、".join(missing)

    mode = values["模式設定(陪伴模式C/劇場模式T)"].upper()

    if mode and mode not in ["C", "T", "陪伴模式", "劇場模式"]:
        return None, "模式設定只能填 C、T、陪伴模式、劇場模式，或留空。"

    if mode == "陪伴模式":
        values["模式設定(陪伴模式C/劇場模式T)"] = "C"

    if mode == "劇場模式":
        values["模式設定(陪伴模式C/劇場模式T)"] = "T"

    return values, None


def save_persona_settings(chat_id, values):
    chat_id = _text_id(chat_id)
    ensure_persona_memory(chat_id)

    db_values = {
        PERSONA_FIELD_MAP[label]: values[label]
        for label in PERSONA_FIELD_LABELS
    }

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE persona_memory
        SET
            mode_setting = %s,
            ai_nickname = %s,
            ai_appearance = %s,
            ai_background = %s,
            ai_reply_style = %s,
            user_nickname = %s,
            user_appearance = %s,
            user_background = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE chat_id = %s
        """,
        (
            db_values["mode_setting"],
            db_values["ai_nickname"],
            db_values["ai_appearance"],
            db_values["ai_background"],
            db_values["ai_reply_style"],
            db_values["user_nickname"],
            db_values["user_appearance"],
            db_values["user_background"],
            chat_id,
        )
    )

    conn.commit()
    conn.close()


def handle_persona_settings(chat_id, text):
    lines = [
        line.strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]

    if lines == [PERSONA_SETTING_COMMAND]:
        return build_persona_form(chat_id)

    values, error = parse_persona_form(text)

    if error:
        return error

    save_persona_settings(chat_id, values)

    return "人格設定已更新。"


def build_persona_prompt(chat_id):
    settings = get_persona_settings(chat_id)

    if not any(settings.values()):
        return ""

    mode = settings["模式設定(陪伴模式C/劇場模式T)"]
    mode_text = ""

    if mode == "C":
        mode_text = "陪伴模式：自然聊天，少用場景與動作描寫。"
    elif mode == "T":
        mode_text = "劇場模式：可以使用場景、動作、表情與氛圍描寫，但不要替使用者決定行動、感受或台詞。"

    return f"""
=== 人格設定 ===
模式設定：{mode_text or mode}
AI暱稱：{settings["AI暱稱"]}
AI外觀：{settings["AI外觀"]}
AI背景：{settings["AI背景"]}
AI回覆風格：{settings["AI回覆風格"]}
User暱稱：{settings["User暱稱"]}
User外觀：{settings["User外觀"]}
User背景：{settings["User背景"]}

以上設定優先於一般回覆風格。空白欄位代表未設定，不要自行補完。
使用者資料只用於理解互動脈絡，不要無故重複或揭露。
"""

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

def add_fact(chat_id, fact):

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO facts_memory
        (chat_id, fact)
        VALUES (%s, %s)
        """,
        (chat_id, fact)        
    )

    conn.commit()
    conn.close()

    #RAN version
    #facts_memory[chat_id].append(fact)

def get_facts(chat_id):

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fact
        FROM facts_memory
        WHERE chat_id=%s
        """,
        (chat_id,)        
    )

    rows = cursor.fetchall()

    conn.close()

    return [row[0] for row in rows]

# =========================
# 短期記憶
# =========================

#RAN version
# chat_memory = defaultdict(lambda:                         
#                            deque(
#                                maxlen=100
#                                )
#                            )

def add_chat(chat_id, role, text):

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_memory
        (chat_id, role, text)
        VALUES (%s, %s, %s)
        """,
        (chat_id, role, text)   
    )

    # ✔ 新增：控制DB最多保留3000筆
    cursor.execute(
        """
        DELETE FROM chat_memory
        WHERE chat_id = %s
        AND id NOT IN (
            SELECT id FROM chat_memory
            WHERE chat_id = %s
            ORDER BY id DESC
            LIMIT 3000
        )
        """,
        (chat_id, chat_id)
    )

    conn.commit()
    conn.close()

    #RAN version
    #chat_memory[chat_id].append({

    #    "role": role,
    #    "text": text

    #})

def get_chat(chat_id):

    chat_id = _text_id(chat_id)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, text
        FROM chat_memory
        WHERE chat_id=%s
        ORDER BY id DESC
        LIMIT 100
        """,
        (chat_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    rows.reverse() # 反轉回原本順序

    return[{
        "role": row[0],
        "text": row[1]
    }
    for row in rows
    ]

    #RAN version
    #return list(
    #    chat_memory[chat_id]
    #)
