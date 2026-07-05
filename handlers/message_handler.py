from services.ai_actions import (
    handle_hidden_keyboard_message,
    process_pending_edit_message,
    send_hidden_ai_action_menu,
)
from services.call_ai import run_ai, run_reply_recovery
from services.commands import send_setting_menu
from services.memory_view import send_memory_view_menu


def handle_message(user_id, bot_id, chat_id, user_text, message_id=None):

    # =========================
    # /hidden Reply Keyboard 按鍵
    # 這些按鍵會以「使用者文字訊息」形式進來，必須先攔截：
    # - 刪掉按鍵文字訊息
    # - 不寫入記憶
    # - 不送 Gemini
    # - 不誤觸 pending edit
    # =========================
    handled = handle_hidden_keyboard_message(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=user_text,
        message_id=message_id,
    )

    if handled:
        return

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
            user_id=user_id,
            source_message_id=message_id
        )
        return

    if user_text in ["/reply", "/回覆"]:
        run_reply_recovery(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id
        )
        return

    if user_text == "/hidden":
        send_hidden_ai_action_menu(
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            source_message_id=message_id
        )
        return

    run_ai(user_id, bot_id, chat_id, user_text, user_message_id=message_id)
