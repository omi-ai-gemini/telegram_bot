from google import genai
from services.style import build_prompt
from services.memory import build_persona_prompt
from config import GEMINI_MODEL

# =========================
# 取得 gemini 回覆（新版）
# =========================
def ask_gemini(gemini_key, chat_id, history, user_text, emotion):

    # =========================
    # 1. 動態初始化（每個 user 都可能不同 key）
    # =========================
    # =========================
    # 2. 組 prompt
    # =========================
    persona_prompt = build_persona_prompt(chat_id)
    prompt = build_prompt(history, user_text, emotion, persona_prompt)


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
