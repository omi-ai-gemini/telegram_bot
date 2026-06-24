from services.commands import send_character_menu, send_setting_menu

# =========================
# callback_query
# =========================
def handle_ui(user_id, bot_id, chat_id, user_text):

    if user_text == "character_setting":
        send_character_menu(bot_id, chat_id)
        return

    if user_text == "back_setting":
        send_setting_menu(bot_id, chat_id)
        return
