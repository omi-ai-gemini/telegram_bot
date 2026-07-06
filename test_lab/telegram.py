from services.telegram_service import send_message


def send_test_message(bot_id, chat_id, text, reply_markup=None):
    return send_message(bot_id, chat_id, text, reply_markup=reply_markup)
