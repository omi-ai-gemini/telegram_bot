from services.ai_actions import (
    build_ai_action_keyboard,
    create_ai_message_action,
    update_action_telegram_message_id,
)
from services.gemini_service import ask_gemini, GEMINI_BLOCKED
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.reply_style import get_reply_style_settings
from services.user_notice import send_once_user_notice
from services.memory_summary import get_memory_context, maintain_memory_after_reply
from services.time_context import get_current_time_context
from services.memory import (
    add_chat,
    get_chat,
    get_facts,
    update_emotion,
    detect_emotion,
    get_emotion
)


def _is_group_chat(chat_id):
    try:
        return int(chat_id) < 0
    except Exception:
        return str(chat_id).startswith("-")


def _extract_telegram_message_id(result):
    if not isinstance(result, dict):
        return None

    message = result.get("result") or {}
    return message.get("message_id")


# =========================
# 取得 AI 回覆並發送
# =========================
def run_ai(user_id: int, bot_id: str, chat_id: int, user_text: str, user_message_id=None):

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
        scope = "group" if _is_group_chat(chat_id) else "private"

        # =========================
        # 先寫入使用者短期記憶
        # 注意：短期記憶不在 add_chat 內直接刪舊資料。
        # 舊資料會在長期摘要成功後才清理。
        # =========================
        user_chat_id = add_chat(
            bot_id,
            chat_id,
            "user",
            user_text,
            user_id=user_id,
            telegram_message_id=user_message_id
        )

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
        # 目前現實時間
        # 每次回覆前即時計算，不寫 DB。
        # =========================
        time_context = get_current_time_context()

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
            memory_context=memory_context,
            time_context=time_context
        )

        # =========================
        # Gemini 回覆被安全層阻擋
        # - 回聊天室 debug 訊息
        # - 不寫入 assistant 短期記憶
        # =========================
        if reply == GEMINI_BLOCKED:
            print("AI BLOCKED SEND: Gemini blocked chat reply")
            send_message(bot_id, chat_id, "內容被安全阻擋")
            return

        # =========================
        # Gemini 沒有回傳可用文字，但不是明確安全阻擋
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
        assistant_chat_id = add_chat(bot_id, chat_id, "assistant", reply, user_id=user_id)

        # =========================
        # 私聊回覆附加小按鈕：改 / 重跑 / 接續
        # 群組先保留延伸，不開放。
        # =========================
        reply_markup = None
        action_id = None

        if scope == "private":
            action_id = create_ai_message_action(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                assistant_chat_id=assistant_chat_id,
                source_user_chat_id=user_chat_id,
                context_chat_id=user_chat_id,
                generation_type="reply"
            )

            if action_id:
                reply_markup = build_ai_action_keyboard(action_id)

        # =========================
        # 回傳 Telegram
        # =========================
        sent = send_message(bot_id, chat_id, reply, reply_markup=reply_markup)
        telegram_message_id = _extract_telegram_message_id(sent)

        if action_id and telegram_message_id:
            update_action_telegram_message_id(action_id, telegram_message_id)

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
