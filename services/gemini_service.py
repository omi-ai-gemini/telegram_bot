from google import genai
from services.style import build_prompt
from config import GEMINI_MODEL

# =========================
# 取得 gemini 回覆（新版）
# =========================
def ask_gemini(gemini_key, history, user_text, emotion):

    # =========================
    # 1. 動態初始化（每個 user 都可能不同 key）
    # =========================
    # =========================
    # 2. 組 prompt
    # =========================
    prompt = build_prompt(history, user_text, emotion)


    # =========================
    # 3. 呼叫 Gemini
    # =========================
    with genai.Client(api_key=gemini_key) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

    print("gemini response:", response.text)

    return response.text

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