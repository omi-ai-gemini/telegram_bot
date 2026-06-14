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
