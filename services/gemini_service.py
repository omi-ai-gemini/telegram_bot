from config import model
from services.style import build_prompt

# =========================
# 取得gemini回覆
# =========================
def ask_gemini(history, user_text):

    prompt = build_prompt(history, user_text)

    response = model.generate_content(
        prompt
    )

    print("gemini response")
    return response.text