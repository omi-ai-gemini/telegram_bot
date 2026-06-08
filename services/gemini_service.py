from config import model

# =========================
# 取得gemini回覆
# =========================
def ask_gemini(user_text):

    response = model.generate_content(
        user_text
    )

    return response.text