from services.call_ai import run_ai
from services.commands import send_setting_menu
from services.privacy_access import ensure_privacy_password_issued, has_privacy_password_issued
from services.privacy_migration import migrate_plaintext_to_encrypted
from services.privacy_session import (
    clear_unlock_code,
    get_unlock_code,
    set_request_context,
    set_unlock_code,
)
from services.telegram_service import send_message


UNLOCK_COMMANDS = ["/解鎖", "/unlock"]
LOCK_COMMANDS = ["/鎖定", "/lock"]


def _is_group_chat(chat_id):
    try:
        return int(chat_id) < 0
    except Exception:
        return str(chat_id).startswith("-")


def _extract_unlock_code(user_text):
    text = str(user_text or "").strip()

    for cmd in UNLOCK_COMMANDS:
        if text == cmd:
            return ""
        if text.startswith(cmd + " "):
            return text[len(cmd):].strip()

    return None


def _handle_unlock_command(user_id, bot_id, chat_id, user_text):
    unlock_code = _extract_unlock_code(user_text)

    if unlock_code is None:
        return False

    if _is_group_chat(chat_id):
        send_message(
            bot_id,
            chat_id,
            "資料庫密碼不要丟在群組。請私訊我輸入：/解鎖 你的資料庫密碼"
        )
        return True

    if not unlock_code:
        send_message(
            bot_id,
            chat_id,
            "請輸入：/解鎖 你的資料庫密碼"
        )
        return True

    set_unlock_code(user_id, bot_id, unlock_code)

    try:
        migrate_plaintext_to_encrypted(user_id, bot_id, chat_id, unlock_code)
    except Exception as exc:
        print("PRIVACY MIGRATION ERROR after unlock:", exc)

    send_message(
        bot_id,
        chat_id,
        "已解鎖。接下來新的記憶、劇本、風格資料會改用你的資料庫密碼加密儲存。"
    )
    return True


def _handle_lock_command(user_id, bot_id, chat_id, user_text):
    text = str(user_text or "").strip()

    if text not in LOCK_COMMANDS:
        return False

    clear_unlock_code(user_id, bot_id)
    send_message(bot_id, chat_id, "已鎖定。之後要寫入或讀取隱私資料，請重新 /解鎖。")
    return True


def handle_message(user_id, bot_id, chat_id, user_text):

    # =========================
    # 本次 request 的隱私上下文
    # =========================
    set_request_context(user_id, bot_id, chat_id)

    # =========================
    # 手動解鎖 / 鎖定
    # =========================
    if _handle_unlock_command(user_id, bot_id, chat_id, user_text):
        return

    if _handle_lock_command(user_id, bot_id, chat_id, user_text):
        return

    # =========================
    # 隱私管理密碼補發
    # =========================
    # 如果是新使用者，這裡會發密碼，並同步放進本機 unlock cache。
    # 如果是舊使用者但 Render 重啟後 cache 消失，這裡不會知道密碼；
    # 後續隱私寫入會自動略過，直到使用者輸入 /解鎖 密碼。
    ensure_privacy_password_issued(user_id, bot_id, chat_id)

    unlock_code = get_unlock_code(user_id, bot_id)

    if unlock_code:
        try:
            migrate_plaintext_to_encrypted(user_id, bot_id, chat_id, unlock_code)
        except Exception as exc:
            print("PRIVACY MIGRATION ERROR:", exc)
    else:
        # 已發過密碼但目前沒解鎖，不再寫明文記憶。
        if has_privacy_password_issued(user_id, bot_id) and not _is_group_chat(chat_id):
            print("PRIVACY LOCKED: user has password but no unlock session", user_id, bot_id)

    if user_text in ["/setting", "/設定"]:
        send_setting_menu(bot_id, chat_id)
        return

    run_ai(user_id, bot_id, chat_id, user_text)
