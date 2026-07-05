from services.ai_actions import process_pending_edit_message
from services.call_ai import run_ai, run_reply_recovery
from services.commands import send_setting_menu
from services.memory_view import send_memory_view_menu


def handle_message(user_id, bot_id, chat_id, user_text, message_id=None):

    # =========================
    # AI 訊息修改模式
    # 使用者按「✏️改」後，下一則文字只拿來替換原 AI 回覆：
    # - 不丟 Gemini
    # - 不寫入 user chat_memory
    # - 修改稿與提示會自動刪除
    # =========================
    handled = process_pending_edit_message(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=user_text,
        user_message_id=message_id
    )

    if handled:
        return

    if user_text in ["/setting", "/設定"]:
        send_setting_menu(
            bot_id,
            chat_id,
            user_id=user_id,
            source_message_id=message_id
        )
        return

    if user_text in ["/memory", "/記憶"]:
        send_memory_view_menu(
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id
        )
        return

    if user_text in ["/reply", "/回覆"]:
        run_reply_recovery(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id
        )
        return

    run_ai(user_id, bot_id, chat_id, user_text, user_message_id=message_id)
