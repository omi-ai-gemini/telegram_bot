from config import model
from services.style import build_prompt

# =========================
# 取得gemini回覆
# =========================
def ask_gemini(history, user_text, emotion):

    prompt = build_prompt(history, user_text, emotion)

    response = model.generate_content(prompt)

    print("gemini response", response.text)

    return response.text