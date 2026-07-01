from services.commands import (
    send_character_menu,
    send_setting_menu,
    send_mode_menu,
    send_memory_menu,
    send_clear_memory_confirm_message,
    send_delete_character_confirm_message,
)
from services.character import (
    update_character_mode,
    delete_character_settings,
)
from services.chat_persona import delete_chat_persona_settings
from services.memory import delete_current_memory
from services.telegram_service import (
    answer_callback_query,
    delete_message,
)

# =========================
# callback_query
# =========================
def handle_ui(user_id, bot_id, chat_id, message_id, user_text, callback_id):

    print("callback", user_text, "message:", message_id)

    # =========================
    # 結束設定
    # 直接刪除目前這則設定選單訊息
    # =========================
    if user_text == "close_setting_menu":

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="已結束設定"
        )
        return

    # =========================
    # 第一層：設定中心 → 人物設定
    # =========================
    if user_text == "character_setting":

        answer_callback_query(bot_id, callback_id)

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 第一層：設定中心 → 記憶設定
    # =========================
    if user_text == "memory_setting":

        answer_callback_query(bot_id, callback_id)

        send_memory_menu(
            bot_id,
            chat_id,
            message_id
        )
        return

    # =========================
    # 記憶設定 → 新增確認訊息
    # =========================
    if user_text == "clear_current_memory":

        answer_callback_query(bot_id, callback_id)

        send_clear_memory_confirm_message(
            bot_id,
            chat_id
        )
        return

    # =========================
    # 確認清除當前記憶
    # 只刪記憶，不刪人物 / 劇本設定
    # =========================
    if user_text == "confirm_clear_current_memory":

        delete_current_memory(bot_id, chat_id)

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="✅ 已清除當前記憶"
        )
        return

    # =========================
    # 取消清除當前記憶
    # =========================
    if user_text == "cancel_clear_current_memory":

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="已取消清除"
        )
        return

    # =========================
    # 模式設定
    # =========================
    if user_text == "character_mode":

        answer_callback_query(bot_id, callback_id)

        send_mode_menu(bot_id, chat_id, message_id)
        return

    if user_text == "mode_chat":

        answer_callback_query(bot_id, callback_id)

        update_character_mode(bot_id, chat_id, "聊天模式")

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            mode="聊天模式",
            user_id=user_id
        )
        return

    if user_text == "mode_theater":

        answer_callback_query(bot_id, callback_id)

        update_character_mode(bot_id, chat_id, "劇場模式")

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            mode="劇場模式",
            user_id=user_id
        )
        return

    # =========================
    # 表單 fallback
    # 正常情況下不會進來，因為設定按鈕會是 url button
    # =========================
    if user_text == "script_setting":

        answer_callback_query(
            bot_id,
            callback_id,
            text="BASE_URL 尚未設定，無法開啟表單"
        )

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 人物設定 → 新增刪除確認訊息
    # =========================
    if user_text == "delete_character":

        answer_callback_query(bot_id, callback_id)

        send_delete_character_confirm_message(
            bot_id,
            chat_id
        )
        return

    # =========================
    # 確認刪除所有設定
    # 目前不分聊天模式 / 劇場模式
    # 會一起刪：
    # - 聊天模式人物設定
    # - 劇本設定
    # - 短期記憶
    # - 長期記憶
    # - 情緒狀態
    # =========================
    if user_text == "confirm_delete_character":

        delete_chat_persona_settings(bot_id, chat_id)

        delete_character_settings(bot_id, chat_id)

        delete_current_memory(bot_id, chat_id)

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="✅ 已刪除所有設定與記憶"
        )
        return

    # =========================
    # 取消刪除所有設定
    # =========================
    if user_text == "cancel_delete_character":

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="已取消刪除"
        )
        return

    # =========================
    # 返回
    # =========================
    if user_text == "back_setting":

        answer_callback_query(bot_id, callback_id)

        send_setting_menu(bot_id, chat_id, message_id)
        return

    if user_text == "back_character":

        answer_callback_query(bot_id, callback_id)

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 未知 callback
    # =========================
    answer_callback_query(
        bot_id,
        callback_id,
        text="未知操作"
    )
