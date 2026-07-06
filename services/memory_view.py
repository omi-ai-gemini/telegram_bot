import os
from urllib.parse import urlencode

from services.memory import (
    delete_chat_memory_item,
    list_important_facts,
    list_recent_chat_memory,
)
from services.memory_summary import delete_memory_summary, list_memory_summaries
from services.setting_auth import create_setting_token, is_group_chat
from services.telegram_service import answer_callback_query, delete_message, edit_message_text, send_message
from services.setting_sessions import save_setting_menu_session_async, pop_setting_menu_session


def _text_id(value):
    return str(value or "").strip()


def _extract_message_id(result):
    if not isinstance(result, dict):
        return None

    message = result.get("result") or {}
    return message.get("message_id")


def _truncate(text, max_len=90):
    text = " ".join(str(text or "").split())

    if len(text) <= max_len:
        return text

    return text[:max_len - 1] + "…"


def _role_label(role):
    role = str(role or "").strip()

    if role == "assistant":
        return "AI"

    if role == "user":
        return "你"

    return role or "未知"


def _important_memory_url(bot_id, chat_id, user_id):
    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url or is_group_chat(chat_id):
        return None

    token = create_setting_token(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        page_type="important_memory"
    )

    if not token:
        return None

    query = urlencode({
        "bot_id": _text_id(bot_id),
        "chat_id": _text_id(chat_id),
        "user_id": _text_id(user_id),
        "token": token,
    })

    return f"{base_url}/setting/important_memory?{query}"


def _send_or_edit(bot_id, chat_id, message_id, text, reply_markup):
    if message_id:
        return edit_message_text(bot_id, chat_id, message_id, text, reply_markup=reply_markup)

    return send_message(bot_id, chat_id, text, reply_markup=reply_markup)


def build_memory_view_menu_markup(bot_id, chat_id, user_id):
    rows = [
        [{"text": "短期記憶 10筆", "callback_data": "mem_view_short"}],
        [{"text": "摘要記憶 6筆", "callback_data": "mem_view_summary"}],
    ]

    url = _important_memory_url(bot_id, chat_id, user_id)

    if url:
        rows.append([{"text": "全部重點記憶", "url": url}])
    else:
        rows.append([{"text": "全部重點記憶", "callback_data": "mem_view_important_fallback"}])

    rows.append([{"text": "❌ 關閉", "callback_data": "mem_close"}])

    return {"inline_keyboard": rows}


def send_memory_view_menu(bot_id, chat_id, user_id, message_id=None, source_message_id=None):
    if is_group_chat(chat_id):
        send_message(bot_id, chat_id, "群組記憶查看暫不開放，請私訊 bot 使用 /memory 或 /記憶")
        return None

    text = (
        "🧠 記憶查看\n\n"
        "可以查看最近 10 筆短期記憶、6 筆摘要記憶。\n"
        "重點記憶會打開既有管理頁。"
    )

    result = _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        text,
        build_memory_view_menu_markup(bot_id, chat_id, user_id)
    )

    # /memory / /記憶 直接叫出選單時，記錄「選單訊息 ↔ 指令訊息」。
    # 從 /setting 進入查看記憶時會沿用同一則設定選單訊息，
    # 原本 /setting 的 session 已存在，不需要在這裡重寫。
    if source_message_id and not message_id:
        menu_message_id = _extract_message_id(result)

        if menu_message_id:
            save_setting_menu_session_async(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                menu_message_id=menu_message_id,
                command_message_id=source_message_id,
            )

    return result


def _render_short_memory(bot_id, chat_id, user_id, message_id):
    rows = list_recent_chat_memory(bot_id, chat_id, limit=10, user_id=user_id)

    if rows:
        lines = ["🧠 最近 10 筆短期記憶", ""]

        for index, item in enumerate(rows, start=1):
            lines.append(
                f"{index}. #{item['id']} {_role_label(item.get('role'))}：{_truncate(item.get('text'))}"
            )
    else:
        lines = ["🧠 最近 10 筆短期記憶", "", "目前沒有短期記憶。"]

    buttons = []

    for item in rows:
        buttons.append([{
            "text": f"刪短期 #{item['id']}",
            "callback_data": f"mem_del_short:{item['id']}"
        }])

    buttons.append([
        {"text": "🔄 刷新", "callback_data": "mem_view_short"},
        {"text": "⬅️ 返回", "callback_data": "mem_view_menu"},
    ])

    return _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "\n".join(lines),
        {"inline_keyboard": buttons}
    )


def _render_summary_memory(bot_id, chat_id, user_id, message_id):
    rows = list_memory_summaries(bot_id, chat_id, limit=6)

    if rows:
        lines = ["🧠 最近 6 筆摘要記憶", ""]

        for index, item in enumerate(rows, start=1):
            lines.append(
                f"{index}. #{item['id']} [{item['start_chat_id']}～{item['end_chat_id']}] {_truncate(item.get('summary'), 120)}"
            )
    else:
        lines = ["🧠 最近 6 筆摘要記憶", "", "目前沒有摘要記憶。"]

    buttons = []

    for item in rows:
        buttons.append([{
            "text": f"刪摘要 #{item['id']}",
            "callback_data": f"mem_del_summary:{item['id']}"
        }])

    buttons.append([
        {"text": "🔄 刷新", "callback_data": "mem_view_summary"},
        {"text": "⬅️ 返回", "callback_data": "mem_view_menu"},
    ])

    return _send_or_edit(
        bot_id,
        chat_id,
        message_id,
        "\n".join(lines),
        {"inline_keyboard": buttons}
    )


def handle_memory_view_callback(user_id, bot_id, chat_id, message_id, callback_data, callback_id):
    if not isinstance(callback_data, str) or not callback_data.startswith("mem_"):
        return False

    if is_group_chat(chat_id):
        answer_callback_query(bot_id, callback_id, text="群組暫不開放記憶查看")
        return True

    if callback_data == "mem_close":
        command_message_id = pop_setting_menu_session(
            bot_id=bot_id,
            chat_id=chat_id,
            menu_message_id=message_id,
            user_id=user_id,
        )

        delete_message(bot_id, chat_id, message_id)

        if command_message_id:
            delete_message(bot_id, chat_id, command_message_id)

        answer_callback_query(bot_id, callback_id, text="已關閉記憶查看")
        return True

    if callback_data == "mem_view_menu":
        answer_callback_query(bot_id, callback_id)
        send_memory_view_menu(bot_id, chat_id, user_id, message_id=message_id)
        return True

    if callback_data == "mem_view_short":
        answer_callback_query(bot_id, callback_id)
        _render_short_memory(bot_id, chat_id, user_id, message_id)
        return True

    if callback_data == "mem_view_summary":
        answer_callback_query(bot_id, callback_id)
        _render_summary_memory(bot_id, chat_id, user_id, message_id)
        return True

    if callback_data == "mem_view_important_fallback":
        answer_callback_query(
            bot_id,
            callback_id,
            text="重點記憶頁面尚未建立，請確認 BASE_URL / SETTING_LINK_SECRET"
        )
        return True

    if callback_data.startswith("mem_del_short:"):
        memory_id = callback_data.split(":", 1)[1]
        ok, msg = delete_chat_memory_item(memory_id, bot_id, chat_id)
        answer_callback_query(bot_id, callback_id, text=msg or ("已刪除" if ok else "刪除失敗"))
        _render_short_memory(bot_id, chat_id, user_id, message_id)
        return True

    if callback_data.startswith("mem_del_summary:"):
        summary_id = callback_data.split(":", 1)[1]
        ok, msg = delete_memory_summary(summary_id, bot_id, chat_id)
        answer_callback_query(bot_id, callback_id, text=msg or ("已刪除" if ok else "刪除失敗"))
        _render_summary_memory(bot_id, chat_id, user_id, message_id)
        return True

    return False
