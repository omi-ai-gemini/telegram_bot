from services.ai_actions import (
    handle_hidden_keyboard_message,
    process_pending_edit_message,
    send_hidden_ai_action_menu,
)
from services.call_ai import run_ai, run_reply_recovery
from services.commands import send_setting_menu
from services.memory_view import send_memory_view_menu
from services.media_ai import queue_text_for_pending_photo
from services.telegram_service import send_message
from services.prompt_debug import send_prompt_debug_link
from test_lab.service import handle_test_lab_message


def handle_message(user_id, bot_id, chat_id, user_text, message_id=None):

    text = str(user_text or "").strip()

    # =========================
    # 明確指令優先處理
    # - 指令不需要先檢查 hidden keyboard / pending edit
    # - 避免指令被前置狀態檢查拖慢
    # =========================
    # =========================
    # Telegram /start
    # - 使用者第一次點開新 bot 時 Telegram 會自動送 /start
    # - 這不是聊天內容，不寫入記憶、不送 Gemini，避免浪費模型次數
    # =========================
    if text == "/start":
        send_message(
            bot_id,
            chat_id,
            "歡迎使用Telemini AI"
        )
        return

    # =========================
    # Prompt Test Lab 子專案分流
    # - /test 進入調教模式
    # - test 模式中的一般文字不進主遊戲 run_ai
    # - 不寫主遊戲 chat_memory / user_config
    # =========================
    if handle_test_lab_message(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=text,
        message_id=message_id,
    ):
        return

    if text in ["/setting", "/設定"]:
        send_setting_menu(
            bot_id=bot_id,
            chat_id=chat_id,
            source_message_id=message_id,
            user_id=user_id,
        )
        return

    if text in ["/memory", "/記憶"]:
        send_memory_view_menu(
            bot_id=bot_id,
            chat_id=chat_id,
            source_message_id=message_id,
            user_id=user_id,
        )
        return

    if text in ["/reply", "/回覆"]:
        run_reply_recovery(user_id, bot_id, chat_id)
        return

    if text in ["/prompt_debug", "/prompt", "/提示除錯"]:
        send_prompt_debug_link(bot_id, chat_id, user_id, compare=False)
        return

    if text in ["/prompt_debug_compare", "/prompt_compare", "/提示比對"]:
        send_prompt_debug_link(bot_id, chat_id, user_id, compare=True)
        return

    if text == "/hidden":
        send_hidden_ai_action_menu(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            source_message_id=message_id,
        )
        return

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

    # =========================
    # 圖片等待 10 秒：後續一般文字先交給圖片緩衝器
    # - 指令、hidden keyboard、修改 AI 文字仍維持上方優先級
    # - 被接收的文字不會先單獨呼叫 Gemini，也不會重複寫入記憶
    # =========================
    if queue_text_for_pending_photo(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=user_text,
        message_id=message_id,
    ):
        return

    run_ai(user_id, bot_id, chat_id, user_text, user_message_id=message_id)
