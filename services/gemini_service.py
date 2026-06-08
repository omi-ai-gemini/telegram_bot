from config import model
from style import build_prompt

# =========================
# 取得gemini回覆
# =========================
def ask_gemini(user_text):

    prompt = build_prompt(user_text)

    response = model.generate_content(
        prompt
    )

    return response.text