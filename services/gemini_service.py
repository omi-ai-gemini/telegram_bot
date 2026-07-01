from google import genai
from services.style import build_prompt
from config import GEMINI_MODEL

# =========================
# 取得 Gemini 回覆
# =========================
def ask_gemini(
    gemini_key,
    history,
    user_text,
    emotion,
    mode="聊天模式",
    chat_persona_settings=None,
    character_settings=None,
    facts=None
):

    # =========================
    # 組 prompt
    # =========================
    prompt = build_prompt(
        history=history,
        user_text=user_text,
        emotion=emotion,
        mode=mode,
        chat_persona_settings=chat_persona_settings,
        character_settings=character_settings,
        facts=facts
    )

    print("DEBUG prompt preview:", prompt[:1200])

    # =========================
    # 呼叫 Gemini
    # =========================
    with genai.Client(api_key=gemini_key) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

    print("gemini response:", response.text)

    return response.text


# =========================
# 摘要短期記憶成長期記憶
# =========================
def summarize_memory(gemini_key, chat_text):

    prompt = f"""
你是一個記憶整理AI。

請把以下對話整理成「可長期記憶的事實」。

規則：
- 只保留穩定資訊（習慣、偏好、身份、長期狀態）
- 不要保留閒聊
- 每行一條
- 用 - 開頭

對話：
{chat_text}
"""

    with genai.Client(api_key=gemini_key) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

    return response.text
