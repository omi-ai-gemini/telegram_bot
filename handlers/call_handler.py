from services.commands import (
    send_character_menu,
    send_setting_menu,
    send_mode_menu
)
from services.character import update_character_mode

# =========================
# callback_query
# =========================
def handle_ui(user_id, bot_id, chat_id, message_id, user_text):

    print("callback", user_text, "message:", message_id)

    if user_text == "character_setting":
        send_character_menu(bot_id, chat_id, message_id)
        return

    if user_text == "character_mode":
        send_mode_menu(bot_id, chat_id, message_id)
        return

    if user_text == "mode_chat":
        update_character_mode(bot_id, chat_id, "聊天模式")
        send_character_menu(bot_id, chat_id, message_id, mode="聊天模式")
        return

    if user_text == "mode_theater":
        update_character_mode(bot_id, chat_id, "劇場模式")
        send_character_menu(bot_id, chat_id, message_id, mode="劇場模式")
        return

    if user_text == "back_setting":
        send_setting_menu(bot_id, chat_id, message_id)
        return

    if user_text == "back_character":
        send_character_menu(bot_id, chat_id, message_id)
        return
