from collections import defaultdict, deque


# =========================
# 人格記憶
# =========================



# =========================
# 情緒記憶
# =========================



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

def add_fact(user_id, fact):
    facts_memory[user_id].append(fact)

# =========================
# 短期記憶
# =========================

chat_memory = defaultdict(lambda:                         
                           deque(maxlen=100)
                           )

def add_chat(user_id, role, text):

    chat_memory[user_id].append({

        "role": role,
        "text": text

    })

def get_chat(user_id):

    return list(
        chat_memory[user_id]
    )