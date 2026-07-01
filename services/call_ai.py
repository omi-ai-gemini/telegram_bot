from services.gemini_service import ask_gemini
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.memory import get_recent_chat
from services.gemini_service import summarize_memory
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.memory import (
    add_chat,
    get_chat,
    get_facts,
    is_memory_command,
    extract_memory_content,
    add_fact,
    update_emotion,
    detect_emotion,
    get_emotion
)


# =========================
# 取得 AI 回覆並發送
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

        # =========================
        # scope 判斷
        # =========================
        scope = "group" if int(chat_id) < 0 else "private"

        # =========================
        # 先寫入使用者短期記憶
        # =========================
        add_chat(bot_id, chat_id, "user", user_text)

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

            if fact:
                add_fact(bot_id, chat_id, scope, fact)

            send_message(bot_id, chat_id, "已記住")
            return

        # =========================
        # 短期記憶
        # =========================
        history = get_chat(bot_id, chat_id)

        # =========================
        # 長期記憶
        # =========================
        facts = get_facts(bot_id, chat_id, scope)

        # =========================
        # 人物 / 劇本設定
        # =========================
        character_settings = get_character_settings(bot_id, chat_id)
        mode = character_settings.get("mode", "聊天模式")

        chat_persona_settings = None

        if mode == "聊天模式":
            chat_persona_settings = get_chat_persona_settings(bot_id, chat_id)

        # =========================
        # 摘要觸發
        # =========================
        if len(history) >= 30:

            recent_rows = get_recent_chat(bot_id, chat_id, limit=30)

            raw_text = "\n".join([
                f"{role}: {text}"
                for role, text in recent_rows
            ])

            summary = summarize_memory(gemini_key, raw_text)

            if summary:

                summary_facts = summary.split("\n")

                for f in summary_facts:
                    f = f.strip("- ").strip()

                    if not f:
                        continue

                    add_fact(bot_id, chat_id, scope, f)

                facts = get_facts(bot_id, chat_id, scope)

        # =========================
        # Gemini 回覆
        # =========================
        reply = ask_gemini(
            gemini_key=gemini_key,
            history=history,
            user_text=user_text,
            emotion=emotion,
            mode=mode,
            chat_persona_settings=chat_persona_settings,
            character_settings=character_settings,
            facts=facts
        )

        # =========================
        # 寫入 AI 短期記憶
        # =========================
        add_chat(bot_id, chat_id, "assistant", reply)

        # =========================
        # 回傳 Telegram
        # =========================
        send_message(bot_id, chat_id, reply)

    except Exception as e:
        print("AI ERROR:", e)
        return
