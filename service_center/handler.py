import re
import threading
import time

from config import SERVICE_CENTER_ADMIN_IDS, SERVICE_CENTER_BOT_ID
from service_center.db import (
    create_announcement,
    list_announcements,
    upsert_service_center_subscriber,
)
from service_center.telegram import (
    answer_callback_query,
    delete_message,
    edit_message_text,
    get_bot_info_by_token,
    send_message,
    setup_game_bot_webhook,
)
from services.bot_router import clear_bot_token_cache
from services.database import save_bot, update_gemini_key


# =========================
# 服務中心 Bot 專用 Handler
# =========================
# 這條路線是完全獨立環境：
# - 不呼叫 Gemini
# - 不寫 chat_memory
# - 不走主遊戲 handlers.message_handler / handlers.call_handler
# - 只處理服務中心：公告、Bot webhook、Gemini API Key 寫入

PENDING_TTL_SECONDS = 10 * 60
_PENDING_INPUTS = {}
_PENDING_LOCK = threading.Lock()


def _text_id(value):
    return str(value or "").strip()


def _pending_key(user_id, chat_id):
    return (_text_id(user_id), _text_id(chat_id))


def _set_pending(user_id, chat_id, action):
    with _PENDING_LOCK:
        _PENDING_INPUTS[_pending_key(user_id, chat_id)] = {
            "action": action,
            "created_at": time.time(),
        }


def _pop_pending(user_id, chat_id):
    key = _pending_key(user_id, chat_id)
    now = time.time()

    with _PENDING_LOCK:
        item = _PENDING_INPUTS.pop(key, None)

    if not item:
        return None

    if now - item.get("created_at", 0) > PENDING_TTL_SECONDS:
        return None

    return item.get("action")


def _clear_pending(user_id, chat_id):
    with _PENDING_LOCK:
        _PENDING_INPUTS.pop(_pending_key(user_id, chat_id), None)


def is_service_center_bot(bot_id):
    """判斷這次 webhook 是否屬於服務中心 bot。"""
    return _text_id(bot_id) == _text_id(SERVICE_CENTER_BOT_ID or "service_center")


def _admin_ids():
    values = []

    for raw in str(SERVICE_CENTER_ADMIN_IDS or "").replace("，", ",").split(","):
        value = raw.strip()
        if value:
            values.append(value)

    return set(values)


def is_service_center_admin(user_id):
    admins = _admin_ids()

    if not admins:
        return False

    return _text_id(user_id) in admins


def _main_menu_markup(user_id=None):
    rows = [
        [
            {"text": "📢 公告事項", "callback_data": "svc:notice"},
            {"text": "🤖 建立Bot", "callback_data": "svc:create_bot"},
        ],
        [
            {"text": "📶 Telemini Wifi", "callback_data": "svc:wifi"},
            {"text": "🔑 Gemini API", "callback_data": "svc:gemini"},
        ],
        [
            {"text": "📘 操作說明", "callback_data": "svc:manual"},
        ],
    ]

    if is_service_center_admin(user_id):
        rows.append([
            {"text": "🛠 管理員", "callback_data": "svc:admin"},
        ])

    return {"inline_keyboard": rows}


def _back_menu_markup():
    return {
        "inline_keyboard": [
            [{"text": "⬅️ 回服務中心", "callback_data": "svc:home"}],
        ]
    }


def _cancel_input_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "取消輸入", "callback_data": "svc:cancel"},
                {"text": "⬅️ 回服務中心", "callback_data": "svc:home"},
            ]
        ]
    }


def _home_text():
    return (
        "Telemini 服務中心\n\n"
        "遊戲上有任何變更會在這裡公告。\n"
        "你也可以在這裡完成新 bot 連線與 Gemini API 設定。\n\n"
        "按鈕說明\n"
        "1. 公告事項：所有歷史公告，最新在最上面\n"
        "2. 建立Bot：教你去 BotFather 建立新的 Telegram bot\n"
        "3. Telemini Wifi：貼上 bot token，自動加入遊戲並設定 webhook\n"
        "4. Gemini API：貼上 Gemini API Key，寫入你的帳號資料\n"
        "5. 操作說明：遊戲內可用的操作和使用方法\n"
    )


def _format_announcement(item):
    if not item:
        return "📢 公告事項\n\n目前沒有公告。"

    label = _text_id(item.get("label")) or "公告"
    title = _text_id(item.get("title")) or "更新公告"
    body = _text_id(item.get("body"))

    return f"📢 [{label}] {title}\n\n{body}"


def _notice_text():
    items = list_announcements(limit=10)

    if not items:
        return "📢 公告事項\n\n目前沒有公告。"

    blocks = ["📢 公告事項\n最新公告會放在最上面"]

    for item in items:
        blocks.append(_format_announcement(item))

    return "\n\n──────────\n\n".join(blocks)


def _create_bot_text():
    return (
        "🤖 建立Bot\n\n"
        "基本流程：\n"
        "1. 到 Telegram 找 @BotFather。\n"
        "2. 輸入 /newbot。\n"
        "3. 幫機器人取名稱。\n"
        "4. 幫機器人設定 username，通常要以 bot 結尾。\n"
        "5. BotFather 會給你一組 bot token。\n\n"
        "拿到 token 後，回到 Telemini Wifi 直接貼上 token，系統會幫你加入遊戲並設定 webhook。"
    )


def _wifi_text():
    return (
        "📶 Telemini Wifi\n\n"
        "請直接貼上 BotFather 給你的 bot token。\n"
        "系統會自動完成：\n"
        "1. 驗證 bot token\n"
        "2. 取得 bot username 作為 bot_id\n"
        "3. 寫入 bot_config\n"
        "4. 設定 webhook 到 Telemini 遊戲程式\n\n"
        "隱私提醒：\n"
        "送出後系統會嘗試刪除你貼 token 的那則訊息。\n"
        "不要在群組或公開聊天室貼 token。"
    )


def _gemini_text():
    return (
        "🔑 Gemini API\n\n"
        "請直接貼上你的 Gemini API Key。\n"
        "系統會寫入你的 user_config，之後你的 bot 對話會使用這組 key。\n\n"
        "隱私提醒：\n"
        "送出後系統會嘗試刪除你貼 API Key 的那則訊息。\n"
        "不要在群組或公開聊天室貼 key。"
    )


def _manual_text():
    return (
        "📘 操作說明\n\n"
        "常用指令：\n"
        "/setting 或 /設定：開啟人物、劇本、記憶與風格設定\n"
        "/memory 或 /記憶：查看近期記憶與摘要記憶\n"
        "/reply 或 /回覆：當上一輪沒有回覆時手動補救\n"
        "/hidden：開發者功能鍵盤\n\n"
        "服務中心：\n"
        "Telemini Wifi 可以加入新的遊戲 bot。\n"
        "Gemini API 可以寫入或更新你的 API Key。"
    )


def _status_text():
    return (
        "📌 服務狀態\n\n"
        "服務中心路線：已啟用\n"
        "Token 來源：環境變數 SERVICE_CENTER_BOT_TOKEN\n"
        "Webhook 路徑：/webhook/service_center\n"
        "主遊戲分流：已隔離\n"
        "Gemini 呼叫：不會執行\n"
        "聊天記憶寫入：不會執行\n"
        "公告資料表：service_center_announcements"
    )


def _admin_text(user_id):
    if not is_service_center_admin(user_id):
        return "這個區塊只開放服務中心管理員使用。"

    return (
        "🛠 管理員\n\n"
        "目前可用：\n"
        "/announce 標籤｜標題｜內容\n\n"
        "新增後會先出現在公告事項裡，下一次台灣時間下午五點會主動推播一次。\n\n"
        "範例：\n"
        "/announce 功能更新｜小改版｜今天更新了服務中心。"
    )


def _text_by_action(action, user_id=None):
    if action == "svc:notice":
        return _notice_text()

    if action == "svc:create_bot":
        return _create_bot_text()

    if action == "svc:wifi":
        return _wifi_text()

    if action == "svc:gemini":
        return _gemini_text()

    if action == "svc:manual":
        return _manual_text()

    if action == "svc:status":
        return _status_text()

    if action == "svc:admin":
        return _admin_text(user_id)

    return _home_text()


def _looks_like_bot_token(text):
    text = _text_id(text)
    return bool(re.match(r"^\d{6,16}:[A-Za-z0-9_-]{20,}$", text))


def _looks_like_gemini_key(text):
    text = _text_id(text)
    # Google API key 常見是 AIza 開頭，但這裡保留一點彈性，避免格式變動直接擋死。
    return len(text) >= 25 and " " not in text and "\n" not in text


def _mask_secret(text, keep_start=6, keep_end=4):
    text = _text_id(text)
    if len(text) <= keep_start + keep_end:
        return "***"
    return f"{text[:keep_start]}...{text[-keep_end:]}"


def _delete_sensitive_user_message(chat_id, message_id):
    if not message_id:
        return

    try:
        delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        print("SERVICE CENTER DELETE SENSITIVE MESSAGE ERROR:", exc, flush=True)


def _handle_bot_token_input(user_id, chat_id, text, message_id):
    _delete_sensitive_user_message(chat_id, message_id)

    token = _text_id(text)

    if not _looks_like_bot_token(token):
        send_message(
            chat_id=chat_id,
            text=(
                "這看起來不像 BotFather 給的 bot token。\n\n"
                "請重新按 Telemini Wifi 後貼上完整 token。"
            ),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    bot_info = get_bot_info_by_token(token)

    if not bot_info:
        send_message(
            chat_id=chat_id,
            text="bot token 驗證失敗，請確認是不是貼到完整 token。",
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    bot_username = _text_id(bot_info.get("username"))

    if not bot_username:
        send_message(
            chat_id=chat_id,
            text="這組 token 可以連線，但沒有取得 bot username，請稍後再試。",
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    bot_id = bot_username

    try:
        save_bot(bot_id, token)
        clear_bot_token_cache(bot_id)
    except Exception as exc:
        print("SERVICE CENTER SAVE GAME BOT ERROR:", exc, flush=True)
        send_message(
            chat_id=chat_id,
            text="bot token 驗證成功，但寫入資料庫失敗。",
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    ok, webhook_result = setup_game_bot_webhook(token, bot_id)

    if not ok:
        send_message(
            chat_id=chat_id,
            text=(
                f"bot 已寫入資料庫，但 webhook 設定失敗。\n\n"
                f"bot_id：{bot_id}\n"
                "請確認 BASE_URL 是否已設定，或稍後再試。"
            ),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    send_message(
        chat_id=chat_id,
        text=(
            "Telemini Wifi 連線完成。\n\n"
            f"bot_id：{bot_id}\n"
            f"bot：@{bot_username}\n"
            "webhook：已設定\n\n"
            "現在可以直接去那隻 bot 傳 /start 測試。"
        ),
        reply_markup=_main_menu_markup(user_id),
    )
    return True


def _handle_gemini_key_input(user_id, chat_id, text, message_id):
    _delete_sensitive_user_message(chat_id, message_id)

    api_key = _text_id(text)

    if not _looks_like_gemini_key(api_key):
        send_message(
            chat_id=chat_id,
            text=(
                "這看起來不像完整的 Gemini API Key。\n\n"
                "請重新按 Gemini API 後貼上完整 key。"
            ),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    try:
        update_gemini_key(_text_id(user_id), api_key)
    except Exception as exc:
        print("SERVICE CENTER SAVE GEMINI KEY ERROR:", exc, flush=True)
        send_message(
            chat_id=chat_id,
            text="Gemini API Key 寫入失敗，請稍後再試。",
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    send_message(
        chat_id=chat_id,
        text=(
            "Gemini API Key 已更新。\n\n"
            f"已保存：{_mask_secret(api_key)}\n"
            "你貼 key 的原始訊息已嘗試刪除。"
        ),
        reply_markup=_main_menu_markup(user_id),
    )
    return True


def _handle_announce_command(user_id, chat_id, text):
    if not is_service_center_admin(user_id):
        send_message(chat_id, "這個指令只開放服務中心管理員使用。")
        return True

    raw = _text_id(text)
    content = raw.replace("/announce", "", 1).strip()

    if not content:
        send_message(
            chat_id,
            "用法：/announce 標籤｜標題｜內容\n例如：/announce 功能更新｜小改版｜今天更新了服務中心。",
        )
        return True

    parts = [p.strip() for p in re.split(r"[｜|]", content, maxsplit=2)]

    if len(parts) < 3:
        send_message(
            chat_id,
            "格式不完整。請用：/announce 標籤｜標題｜內容",
        )
        return True

    ann_id = create_announcement(label=parts[0], title=parts[1], body=parts[2])

    if not ann_id:
        send_message(chat_id, "公告新增失敗。")
        return True

    send_message(chat_id, f"公告已新增：#{ann_id}\n會在下一次台灣時間下午五點主動推播一次。", reply_markup=_main_menu_markup(user_id))
    return True


def handle_service_center_message(user_id, bot_id, chat_id, user_text, message_id=None):
    """處理服務中心 bot 的文字訊息。"""
    upsert_service_center_subscriber(user_id, chat_id)
    text = _text_id(user_text)

    if text in ["/cancel", "/取消", "取消"]:
        _clear_pending(user_id, chat_id)
        send_message(
            chat_id=chat_id,
            text="已取消目前輸入。",
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    if text.startswith("/announce"):
        return _handle_announce_command(user_id, chat_id, text)

    if text == "/start":
        send_message(
            chat_id=chat_id,
            text=_home_text(),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    if text in ["/menu", "/服務中心", "/help", "/manual", "/說明"]:
        send_message(
            chat_id=chat_id,
            text=_home_text(),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    if text == "/status":
        send_message(
            chat_id=chat_id,
            text=_status_text(),
            reply_markup=_back_menu_markup(),
        )
        return True

    pending_action = _pop_pending(user_id, chat_id)

    if pending_action == "awaiting_bot_token":
        return _handle_bot_token_input(user_id, chat_id, text, message_id)

    if pending_action == "awaiting_gemini_key":
        return _handle_gemini_key_input(user_id, chat_id, text, message_id)

    # 沒有等待輸入時，不自動把疑似 key/token 寫入，避免誤觸。
    send_message(
        chat_id=chat_id,
        text="這裡是 Telemini 服務中心。請使用 /menu 開啟服務選單。",
        reply_markup=_main_menu_markup(user_id),
    )
    return True


def handle_service_center_callback(user_id, bot_id, chat_id, message_id, callback_data, callback_id=None):
    """處理服務中心 bot 的 inline button。"""
    upsert_service_center_subscriber(user_id, chat_id)
    action = _text_id(callback_data)

    if callback_id:
        answer_callback_query(callback_id)

    if not action.startswith("svc:"):
        return True

    if action == "svc:home":
        _clear_pending(user_id, chat_id)
        edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_home_text(),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    if action == "svc:cancel":
        _clear_pending(user_id, chat_id)
        edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="已取消目前輸入。\n\n" + _home_text(),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    if action == "svc:wifi":
        _set_pending(user_id, chat_id, "awaiting_bot_token")
        edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_wifi_text(),
            reply_markup=_cancel_input_markup(),
        )
        return True

    if action == "svc:gemini":
        _set_pending(user_id, chat_id, "awaiting_gemini_key")
        edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_gemini_text(),
            reply_markup=_cancel_input_markup(),
        )
        return True

    edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=_text_by_action(action, user_id=user_id),
        reply_markup=_back_menu_markup(),
    )
    return True
