from services.gemini_service import ask_gemini
from services.telegram_service import send_message
from services.memory import(
    add_chat,
    get_chat,
    is_memory_command,
    extract_memory_content,
    add_fact,
    update_emotion,
    detect_emotion,
    get_emotion

)

# =========================
# 取得AI回覆並發送
# =========================
def run_ai(chat_id, user_text):

    try:
        
        #add_chat(chat_id, "user", user_text)   #{已移到webhook}

        #情緒記憶
        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)

        emotion = get_emotion(chat_id)

        # ✔ DEBUG LOG（新增）
        print(f"[EMOTION DEBUG] chat_id={chat_id}")
        print(f"[EMOTION DEBUG] input_text={user_text}")
        print(f"[EMOTION DEBUG] delta={delta}")
        print(f"[EMOTION DEBUG] mood={emotion['mood']}")
        print(f"[EMOTION DEBUG] level={emotion['level']}")

        #長期記憶
        if is_memory_command(user_text):

            fact = extract_memory_content(user_text)

            add_fact(chat_id, fact)

            #測試長期記憶通過
            send_message(chat_id, "已記住")
            return

        #短期記憶
        history = get_chat(chat_id)

        #取得AI回覆
        reply = ask_gemini(history, user_text, emotion)

        #AI回覆寫入短期記憶
        add_chat(chat_id, "assistant", reply)

        send_message(chat_id, reply)

    except Exception as e:

        print("AI ERROR:", e)

        return