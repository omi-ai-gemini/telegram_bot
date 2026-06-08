from services.gemini_service import ask_gemini
from services.telegram_service import send_message
from services.memory import(
    is_memory_command,
    extract_memory_content,
    add_fact
)

# =========================
# 防timeout 長期記憶指令
# =========================
def run_ai(chat_id, user_text):

    try:
        if is_memory_command(user_text):

            fact = extract_memory_content(user_text)

            add_fact(chat_id, fact)

        # 記憶指令保存後，繼續正常對話
        reply = ask_gemini(user_text)

        send_message(chat_id, reply)

    except Exception as e:

        print("AI ERROR:", e)

        return