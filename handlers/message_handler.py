from services.call_ai import run_ai
from services.commands import send_setting_menu


def handle_message(user_id, bot_id, chat_id, user_text):

    if user_text in ["/setting", "/設定"]:
        send_setting_menu(bot_id, chat_id)
        return

    run_ai(user_id, bot_id, chat_id, user_text)
