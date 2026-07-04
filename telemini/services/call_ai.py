from services.gemini_service import ask_gemini
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.reply_style import get_reply_style_settings
from services.user_notice import send_once_user_notice
from services.memory_summary import get_memory_context, maintain_memory_after_reply
from services.memory import (
    add_chat,
    get_chat,
    get_facts,
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
        # 全體使用者一次性公告
        # 每個 user + bot 只會收到一次
        # =========================
        send_once_user_notice(user_id, bot_id, chat_id)

        # =========================
        # scope 判斷
        # =========================
        scope = "group" if int(chat_id) < 0 else "private"

        # =========================
        # 先寫入使用者短期記憶
        # 注意：短期記憶不在 add_chat 內直接刪舊資料。
        # 舊資料會在長期摘要成功後才清理。
        # =========================
        add_chat(bot_id, chat_id, "user", user_text, user_id=user_id)

        # =========================
        # 情緒記憶
        # =========================
        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)
        emotion = get_emotion(chat_id)

        # =========================
        # 一般文字不再觸發「手動記憶」
        # 重點記憶統一從設定中心的「⭐ 重點記憶」寫入 facts_memory。
        # =========================

        # =========================
        # 短期記憶
        # =========================
        history = get_chat(bot_id, chat_id, user_id=user_id)

        # =========================
        # 重點記憶
        # =========================
        facts = get_facts(bot_id, chat_id, scope, user_id=user_id, limit=20)

        # =========================
        # 摘要型長期記憶
        # =========================
        memory_context = get_memory_context(bot_id, chat_id, scope, user_id=user_id)

        # =========================
        # 人物 / 劇本設定
        # =========================
        character_settings = get_character_settings(bot_id, chat_id, user_id=user_id)
        mode = character_settings.get("mode", "聊天模式")

        chat_persona_settings = None

        if mode == "聊天模式":
            chat_persona_settings = get_chat_persona_settings(bot_id, chat_id, user_id=user_id)

        # =========================
        # 獨立回覆風格設定
        # 聊天 / 劇場各自保存，不跟人物或劇本綁定
        # =========================
        reply_style_settings = get_reply_style_settings(
            bot_id=bot_id,
            chat_id=chat_id,
            style_type=mode,
            user_id=user_id
        )

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
            reply_style_settings=reply_style_settings,
            facts=facts,
            memory_context=memory_context
        )

        # =========================
        # Gemini 沒有回傳可用文字時
        # - 不傳假訊息
        # - 不寫入 assistant 短期記憶
        # - 詳細原因看 Render 的 GEMINI DEBUG log
        # =========================
        if not reply:
            print("AI SKIP SEND: Gemini returned empty reply")
            return

        # =========================
        # 寫入 AI 短期記憶
        # =========================
        add_chat(bot_id, chat_id, "assistant", reply, user_id=user_id)

        # =========================
        # 回傳 Telegram
        # =========================
        send_message(bot_id, chat_id, reply)

        # =========================
        # 記憶維護
        # - 每 100 則短期訊息摘要一次（約 50 輪對話）
        # - 摘要成功後才清理超過 100 則的短期訊息
        # - 長期摘要過多時再封存摘要
        # =========================
        maintain_memory_after_reply(gemini_key, bot_id, chat_id, user_id=user_id)

    except Exception as e:
        print("AI ERROR:", e)
        return
