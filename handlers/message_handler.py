from services.gemini_service import ask_gemini
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.memory import get_recent_chat
from services.memory import add_fact
from services.gemini_service import summarize_memory
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
def run_ai(user_id: int, bot_id: str, chat_id: int, user_text: str):

    try:
        
        #add_chat(chat_id, "user", user_text)   #{已移到webhook}

        # =========================
        # 1. 取得 DB 資料
        # =========================
        gemini_key = get_gemini_key(user_id)

        bot_token = get_bot_token(bot_id)

        if not gemini_key or not bot_token:
            send_message(
                bot_id,
                chat_id,
                f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}"
            )
            #print("❌ missing key/token")
            return

        # =========================
        # 2. 情緒記憶
        # =========================
        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)

        emotion = get_emotion(chat_id)

        # ✔ DEBUG LOG（新增）
        #print(f"[EMOTION DEBUG] chat_id={chat_id}")
        #print(f"[EMOTION DEBUG] input_text={user_text}")
        #print(f"[EMOTION DEBUG] delta={delta}")
        #print(f"[EMOTION DEBUG] mood={emotion['mood']}")
        #print(f"[EMOTION DEBUG] level={emotion['level']}")

        # debug（可刪）
        print(f"[EMOTION] chat_id={chat_id}")
        print(f"[EMOTION] text={user_text}")
        print(f"[EMOTION] mood={emotion['mood']} level={emotion['level']}")

        # =========================
        # 3. 長期記憶
        # =========================
        if is_memory_command(user_text):

            fact = extract_memory_content(user_text)

            scope = "group" if int(chat_id) < 0 else "private"

            add_fact(bot_id=bot_id, chat_id=chat_id, scope=scope, fact=fact)

            #測試長期記憶通過
            send_message(bot_id, chat_id, "已記住")
            return

        # =========================
        # 🧠 1. 取得短期記憶
        # =========================
        history = get_chat(bot_id, chat_id)

        # =========================
        # 🧠 2. 記憶壓縮觸發條件
        # =========================
        if len(history) >= 30:

            raw_text = "\n".join([
                f"{h['role']}: {h['text']}"
                for h in history
            ])

            summary = summarize_memory(gemini_key, raw_text)

            scope = "group" if int(chat_id) < 0 else "private"

            facts = summary.split("\n")

            for f in facts:
                f = f.strip("- ").strip()
                if not f:
                    continue

                add_fact(bot_id, chat_id, scope, f)

        # =========================
        # 5. 呼叫 Gemini
        # =========================
        reply = ask_gemini(gemini_key=gemini_key, history=history, user_text=user_text, emotion=emotion)

        # =========================
        # 6. 寫入記憶
        # =========================
        add_chat(chat_id, "assistant", reply)

        # =========================
        # 7. 回 Telegram
        # =========================
        send_message(bot_id, chat_id, reply)

    except Exception as e:

        print("AI ERROR:", e)
        #send_message(chat_id, "❌ 系統錯誤")

        return