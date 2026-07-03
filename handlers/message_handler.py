from services.call_ai import run_ai
from services.commands import send_setting_menu
from services.privacy_access import ensure_privacy_password_issued


def handle_message(user_id, bot_id, chat_id, user_text):

    # =========================
    # 隱私管理密碼補發
    # =========================
    # 每個 user_id + bot_id 只會真正發一次。
    # 已發放者會進記憶體快取，避免每次 Gemini 回應前都查 DB。
    ensure_privacy_password_issued(user_id, bot_id, chat_id)

    if user_text in ["/setting", "/設定"]:
        send_setting_menu(bot_id, chat_id)
        return

    run_ai(user_id, bot_id, chat_id, user_text)
