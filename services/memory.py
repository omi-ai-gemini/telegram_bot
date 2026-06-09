from collections import defaultdict, deque
from collections import defaultdict


# =========================
# 人格記憶
# =========================



# =========================
# 情緒記憶
# =========================

emotion_memory = defaultdict(lambda: {
    "mood": "neutral",      # happy/sad/angry/neutral
    "level": 0              # -10~10
})

def update_emotion(chat_id, delta: int):
    """
    delta:
    + 正面情緒
    - 負面情緒
    """

    emotion = emotion_memory[chat_id]

    emotion["level"] += delta

    #限制範圍
    if emotion["level"] > 10:
        emotion["level"] = 10
    if emotion["level"] < -10:
        emotion["level"] = -10
    
    #更新mood
    if emotion["level"] >= 5:
        emotion["mood"] = "happy"
    elif emotion["level"] <= -5:
        emotion["mood"] = "angry"
    else:
        emotion["mood"] = "neutral"

def get_emotion(chat_id):
    
    return emotion_memory[chat_id]

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

facts_memory = defaultdict(list)

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
    facts_memory[chat_id].append(fact)

# =========================
# 短期記憶
# =========================

chat_memory = defaultdict(lambda:                         
                           deque(
                               maxlen=100
                               )
                           )

def add_chat(chat_id, role, text):

    chat_memory[chat_id].append({

        "role": role,
        "text": text

    })

def get_chat(chat_id):

    return list(
        chat_memory[chat_id]
    )