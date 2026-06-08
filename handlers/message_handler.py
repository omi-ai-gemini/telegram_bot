from services.gemini_service import ask_gemini
from services.telegram_service import send_message

# =========================
# 防timeout
# =========================
def run_ai(chat_id, user_text):

    try:
        reply = ask_gemini(user_text)

        send_message(chat_id, reply)

    except Exception as e:

        print("AI ERROR:", e)

        send_message(
            chat_id,
             "發生錯誤，請稍後再試"
        )