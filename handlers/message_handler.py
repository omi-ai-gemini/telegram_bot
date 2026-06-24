from services.gemini_service import ask_gemini
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.memory import get_recent_chat
from services.gemini_service import summarize_memory
from services.commands import send_setting_menu
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

        gemini_key = get_gemini_key(user_id)

        bot_token = get_bot_token(bot_id)

        if not gemini_key or not bot_token:
            send_message(
                bot_id,
                chat_id,
                f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}"
            )
            return
        
        #if user_text == "/setting":
        if user_text in ["/setting", "/設定"]:

            send_setting_menu(bot_token, chat_id)

            return

        # =========================
        # 情緒記憶
        # =========================
        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)
        emotion = get_emotion(chat_id)

        # =========================
        # 長期記憶（手動記憶指令）
        # =========================
        if is_memory_command(user_text):

            fact = extract_memory_content(user_text)
            scope = "group" if int(chat_id) < 0 else "private"

            add_fact(bot_id, chat_id, scope, fact)

            send_message(bot_id, chat_id, "已記住")
            return

        # =========================
        # 短期記憶
        # =========================
        history = get_chat(bot_id, chat_id)

        # =========================
        # 🧠 摘要觸發
        # =========================
        if len(history) >= 30:

            recent_rows = get_recent_chat(bot_id, chat_id, limit=30)

            raw_text = "\n".join([
                f"{role}: {text}"
                for role, text in recent_rows
            ])

            summary = summarize_memory(gemini_key, raw_text)

            if summary:

                scope = "group" if int(chat_id) < 0 else "private"

                facts = summary.split("\n")

                for f in facts:
                    f = f.strip("- ").strip()
                    if not f:
                        continue

                    add_fact(bot_id, chat_id, scope, f)

        # =========================
        # Gemini 回覆
        # =========================
        reply = ask_gemini(
            gemini_key=gemini_key,
            history=history,
            user_text=user_text,
            emotion=emotion
        )

        # =========================
        # 寫入短期記憶（✔ 修正重點）
        # =========================
        add_chat(bot_id, chat_id, "assistant", reply)

        # =========================
        # 回傳 Telegram
        # =========================
        send_message(bot_id, chat_id, reply)

    except Exception as e:
        print("AI ERROR:", e)
        return