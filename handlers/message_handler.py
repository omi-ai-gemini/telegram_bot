from services.gemini_service import ask_gemini
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.commands import handle_command
from services.memory import (
    add_chat,
    get_chat,
    is_memory_command,
    extract_memory_content,
    add_fact,
    update_emotion,
    detect_emotion,
    get_emotion,
)


def run_ai(user_id: int, bot_id: str, chat_id: int, user_text: str):
    try:
        bot_token = get_bot_token(bot_id)

        if not bot_token:
            send_message(
                bot_id,
                chat_id,
                f"設定資料缺失:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}",
            )
            return

        command_reply = handle_command(chat_id, user_text)

        if command_reply is not None:
            send_message(bot_id, chat_id, command_reply)
            return

        gemini_key = get_gemini_key(user_id)

        if not gemini_key:
            send_message(
                bot_id,
                chat_id,
                f"設定資料缺失:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}",
            )
            return

        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)
        emotion = get_emotion(chat_id)

        print(f"[EMOTION] chat_id={chat_id}")
        print(f"[EMOTION] text={user_text}")
        print(f"[EMOTION] mood={emotion['mood']} level={emotion['level']}")

        if is_memory_command(user_text):
            fact = extract_memory_content(user_text)
            add_fact(chat_id, fact)
            send_message(bot_id, chat_id, "已記住。")
            return

        history = get_chat(chat_id)

        reply = ask_gemini(
            gemini_key=gemini_key,
            chat_id=chat_id,
            history=history,
            user_text=user_text,
            emotion=emotion,
        )

        add_chat(chat_id, "assistant", reply)
        send_message(bot_id, chat_id, reply)

    except Exception as e:
        print("AI ERROR:", e)
        return
