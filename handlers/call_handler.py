from services.ai_actions import (
    run_continue_in_thread,
    run_regenerate_in_thread,
    run_reply_ai_message_in_thread,
    start_edit_ai_message,
)
from services.memory_view import handle_memory_view_callback
from services.commands import (
    send_character_menu,
    send_setting_menu,
    send_mode_menu,
    send_memory_menu,
    send_reply_style_menu,
    send_start_script_confirm_menu,
    send_clear_memory_confirm_message,
    send_delete_character_confirm_message,
    send_delete_reply_style_confirm_message,
)
from services.character import (
    get_script_opening_status,
    mark_script_opening_sent,
    update_character_mode,
    delete_character_settings,
)
from services.chat_persona import delete_chat_persona_settings
from services.reply_style import delete_reply_style_settings
from services.memory import add_chat, delete_current_memory
from services.setting_sessions import pop_setting_menu_session
from services.telegram_service import (
    send_message,
    answer_callback_query,
    delete_message,
)


def _setting_fallback_text(chat_id):
    try:
        is_group = int(chat_id) < 0
    except Exception:
        is_group = str(chat_id).startswith("-")

    if is_group:
        return "群組設定頁暫不開放，請私訊 bot 使用 /設定"

    return "設定連結尚未建立，請確認 BASE_URL / SETTING_LINK_SECRET"


# =========================
# 傳送劇本開場白
# - 傳送到 Telegram
# - 寫入短期記憶 role=assistant
# - 標記 opening_sent=True
# =========================
def _send_script_opening(bot_id, chat_id):

    opening_status = get_script_opening_status(bot_id, chat_id)
    opening_text = opening_status.get("opening_text", "").strip()

    if not opening_text:
        return False

    send_message(
        bot_id,
        chat_id,
        opening_text
    )

    add_chat(
        bot_id,
        chat_id,
        "assistant",
        opening_text
    )

    mark_script_opening_sent(
        bot_id,
        chat_id
    )

    return True


# =========================
# callback_query
# =========================
def handle_ui(user_id, bot_id, chat_id, message_id, user_text, callback_id):


    print("callback", user_text, "message:", message_id)

    # =========================
    # AI 回覆下方小按鈕：修改 / 重跑 / 接續
    # callback_data：ai_edit:<id> / ai_regen:<id> / ai_continue:<id>
    # 群組先保留延伸，不開放；實際限制在 ai_actions 內也會再檢查。
    # =========================
    if isinstance(user_text, str) and user_text.startswith("ai_reply:"):
        action_id = user_text.split(":", 1)[1]

        answer_callback_query(
            bot_id,
            callback_id,
            text="正在補送這句話"
        )

        run_reply_ai_message_in_thread(user_id, bot_id, chat_id, action_id)
        return

    if isinstance(user_text, str) and user_text.startswith("ai_edit:"):
        action_id = user_text.split(":", 1)[1]
        ok, text = start_edit_ai_message(user_id, bot_id, chat_id, action_id)

        answer_callback_query(
            bot_id,
            callback_id,
            text=text or ("請輸入修改後文字" if ok else "這則回覆已無法操作")
        )
        return

    if isinstance(user_text, str) and user_text.startswith("ai_regen:"):
        action_id = user_text.split(":", 1)[1]

        answer_callback_query(
            bot_id,
            callback_id,
            text="正在重跑這句話"
        )

        run_regenerate_in_thread(user_id, bot_id, chat_id, action_id)
        return

    if isinstance(user_text, str) and user_text.startswith("ai_thought_missing:"):
        answer_callback_query(
            bot_id,
            callback_id,
            text="推理摘要網頁連結尚未建立，請確認 BASE_URL 環境變數",
            show_alert=True
        )
        return

    if isinstance(user_text, str) and user_text.startswith("ai_continue:"):
        action_id = user_text.split(":", 1)[1]

        answer_callback_query(
            bot_id,
            callback_id,
            text="正在接續下一句"
        )

        run_continue_in_thread(user_id, bot_id, chat_id, action_id)
        return

    # =========================
    # 記憶查看按鈕：/memory / /記憶
    # =========================
    if handle_memory_view_callback(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        message_id=message_id,
        callback_data=user_text,
        callback_id=callback_id
    ):
        return

    # =========================
    # 最上層：結束設定
    # 直接刪除目前這則設定選單訊息
    # 如果這個選單是由 /setting 或 /設定 開出來，也順手刪掉使用者那則指令。
    # =========================
    if user_text == "close_setting_menu":

        command_message_id = pop_setting_menu_session(
            bot_id=bot_id,
            chat_id=chat_id,
            menu_message_id=message_id,
            user_id=user_id
        )

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        if command_message_id:
            delete_message(
                bot_id,
                chat_id,
                command_message_id
            )

        answer_callback_query(
            bot_id,
            callback_id,
            text="已結束設定"
        )
        return

    # =========================
    # 第一層：設定中心 → 開始劇本
    # =========================
    if user_text == "start_script":

        opening_status = get_script_opening_status(bot_id, chat_id)
        status = opening_status.get("status")

        # =========================
        # 沒有開場白：只刪選單，不傳訊息
        # =========================
        if status == "no_opening":

            delete_message(
                bot_id,
                chat_id,
                message_id
            )

            answer_callback_query(
                bot_id,
                callback_id,
                text="此劇本沒有開場白"
            )
            return

        # =========================
        # 已開場：進入再次發送確認選單
        # =========================
        if status == "started":

            answer_callback_query(bot_id, callback_id)

            send_start_script_confirm_menu(
                bot_id,
                chat_id,
                message_id
            )
            return

        # =========================
        # 未開場：刪選單、傳開場白、寫短期記憶
        # =========================
        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        sent = _send_script_opening(
            bot_id,
            chat_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="劇本已開始" if sent else "此劇本沒有開場白"
        )
        return

    # =========================
    # 確認再次發送開場白
    # =========================
    if user_text == "confirm_restart_script":

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        sent = _send_script_opening(
            bot_id,
            chat_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="已再次發送開場白" if sent else "此劇本沒有開場白"
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
    # 第一層：設定中心 → 回覆風格
    # =========================
    if user_text == "reply_style_setting":

        answer_callback_query(bot_id, callback_id)

        send_reply_style_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 回覆風格表單 fallback
    # 正常情況下不會進來，因為設定按鈕會是 url button
    # =========================
    if user_text in ["reply_style_chat", "reply_style_theater"]:

        answer_callback_query(
            bot_id,
            callback_id,
            text=_setting_fallback_text(chat_id)
        )

        send_reply_style_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 回覆風格 → 新增刪除確認訊息
    # =========================
    if user_text == "delete_reply_style":

        answer_callback_query(bot_id, callback_id)

        send_delete_reply_style_confirm_message(
            bot_id,
            chat_id
        )
        return

    # =========================
    # 確認刪除回覆風格
    # 只刪回覆風格，不刪人物 / 劇本 / 記憶
    # =========================
    if user_text == "confirm_delete_reply_style":

        delete_reply_style_settings(bot_id, chat_id)

        delete_message(
            bot_id,
            chat_id,
            message_id
        )

        answer_callback_query(
            bot_id,
            callback_id,
            text="✅ 已刪除自訂回覆風格"
        )
        return

    # =========================
    # 取消刪除回覆風格
    # =========================
    if user_text == "cancel_delete_reply_style":

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
    # 第一層：設定中心 → 記憶設定
    # =========================
    if user_text == "memory_setting":

        answer_callback_query(bot_id, callback_id)

        send_memory_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
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
    # 只刪記憶，不刪人物 / 劇本 / 回覆風格
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
    # 人物 / 劇本表單 fallback
    # 正常情況下不會進來，因為設定按鈕會是 url button
    # =========================
    if user_text == "script_setting":

        answer_callback_query(
            bot_id,
            callback_id,
            text=_setting_fallback_text(chat_id)
        )

        send_character_menu(
            bot_id,
            chat_id,
            message_id,
            user_id=user_id
        )
        return

    # =========================
    # 重點記憶表單 fallback
    # 正常情況下不會進來，因為設定按鈕會是 url button
    # =========================
    if user_text == "important_memory_setting":

        answer_callback_query(
            bot_id,
            callback_id,
            text=_setting_fallback_text(chat_id)
        )

        send_memory_menu(
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
    # 確認刪除人物 / 劇本設定
    # 會刪：
    # - 聊天模式人物設定
    # - 劇本設定
    # - 短期記憶
    # - 長期記憶
    # - 情緒狀態
    # 不會刪：
    # - 回覆風格
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
            text="✅ 已刪除人物 / 劇本設定與記憶"
        )
        return

    # =========================
    # 取消刪除人物 / 劇本設定
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
