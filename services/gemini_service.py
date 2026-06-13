import google.generativeai as genai
from services.style import build_prompt
from config import GEMINI_MODEL

# =========================
# 取得 gemini 回覆（新版）
# =========================
def ask_gemini(gemini_key, history, user_text, emotion):

    # =========================
    # 1. 動態初始化（每個 user 都可能不同 key）
    # =========================
    genai.configure(api_key=gemini_key)

    model = genai.GenerativeModel(GEMINI_MODEL)


    # =========================
    # 2. 組 prompt
    # =========================
    prompt = build_prompt(history, user_text, emotion)


    # =========================
    # 3. 呼叫 Gemini
    # =========================
    response = model.generate_content(prompt)

    print("gemini response:", response.text)

    return response.text
