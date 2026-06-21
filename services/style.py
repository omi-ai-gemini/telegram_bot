BASE_STYLE = """
你是使用者設定的 AI 聊天角色。
回覆時要自然、符合上下文，並優先遵守人格設定。
如果尚未設定人格，維持一般 AI 聊天模式，不要自行假設人物背景。
"""

RESPONSE_RULES = """
回覆規則：
1. 使用繁體中文，語氣自然，偏台灣日常用語。
2. 不要提到你正在讀取 prompt、資料庫或系統設定。
3. 不要無故重複使用者資料。
4. 劇場模式可以描寫 AI 自己的動作、表情、語氣與場景，但不要替使用者決定行動、感受或台詞。
5. 陪伴模式以一般聊天為主，少用旁白與動作描寫。
"""


def build_prompt(history, user_text, emotion, persona_prompt=""):
    history_text = ""

    for msg in history:
        history_text += f"{msg['role']}: {msg['text']}\n"

    prompt = f"""
{BASE_STYLE}

{RESPONSE_RULES}

{persona_prompt}

=== 情緒狀態 ===
情緒：{emotion["mood"]}
強度：{emotion["level"]}

=== 對話紀錄 ===
{history_text}

使用者輸入：
{user_text}

請根據以上資訊回覆：
"""

    return prompt
