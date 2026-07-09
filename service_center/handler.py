from config import SERVICE_CENTER_ADMIN_IDS, SERVICE_CENTER_BOT_ID
from service_center.telegram import answer_callback_query, edit_message_text, send_message


# =========================
# 服務中心 Bot 專用 Handler
# =========================
# 這條路線是完全獨立環境：
# - 不呼叫 Gemini
# - 不寫 chat_memory
# - 不寫 user_config
# - 不查 bot_config
# - 不走主遊戲 handlers.message_handler / handlers.call_handler


def _text_id(value):
    return str(value or "").strip()


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


def _home_text():
    return (
        "Telemini 服務中心\n\n"
        "遊戲上有任何變更會在這裡公告。\n"
        "但前提是我要記得或是有空來更新公告\n\n"
        "按鈕說明\n"
        "1. 公告事項：所有歷史公告\n"
        "2. 建立Bot：我盡量簡單的告訴你怎麼創建新的機器人\n"
        "3. Telemini Wifi：新的機器人連線到遊戲程式\n"
        "4. Gemini API：新增或更改AI連線\n"
        "5. 操作說明：遊戲內可用的操作和使用方法\n"
    )


def _notice_text():
    return (
        "📢 公告事項\n\n"
        "最新公告會放在最上面\n"
    )


def _create_bot_text():
    return (
        "🤖 建立Bot\n\n"
        "我會盡量用最簡單的方式告訴你怎麼創建新的機器人。\n\n"
        "基本流程：\n"
        "1. 到 Telegram 找 @BotFather。\n"
        "2. 輸入 /newbot。\n"
        "3. 幫機器人取名稱。\n"
        "4. 幫機器人設定 username，通常要以 bot 結尾。\n"
        "5. BotFather 會給你一組 token。\n\n"
        "拿到 token 後，再回到 Telemini Wifi 把新的機器人連線到遊戲程式。"
    )


def _wifi_text():
    return (
        "📶 Telemini Wifi\n\n"
        "新的機器人連線到遊戲程式。\n\n"
        "這裡之後會負責：\n"
        "- 接收 BotFather 給你的 bot token。\n"
        "- 驗證這隻 bot 是否能正常使用。\n"
        "- 把新 bot 的 webhook 接到 Telemini 遊戲程式。\n"
        "- 讓新 bot 可以進入主遊戲流程。\n\n"
        "目前先完成服務中心按鈕入口，下一步再接 token 輸入與自動連線流程。"
    )


def _gemini_text():
    return (
        "🔑 Gemini API\n\n"
        "後續會接在這裡：\n"
        "- 使用者提交 Gemini API Key\n"
        "- 寫入既有 user_config\n"
        "- 清除 key 快取\n"
        "- 自動刪除含 key 的訊息\n\n"
        "這一步先不新增 table。"
    )


def _manual_text():
    return (
        "📘 操作說明\n\n"
        "後續會把 manual 網頁的內容搬到這裡，變成 Telegram 內的操作中心。\n\n"
        "預計分類：\n"
        "- 建立 AI Bot\n"
        "- 建立遊戲 Bot\n"
        "- 設定 Gemini API\n"
        "- 常見錯誤排查\n"
        "- 更新公告"
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
        "服務中心專用 table：目前不建立"
    )


def _admin_text(user_id):
    if not is_service_center_admin(user_id):
        return "這個區塊只開放服務中心管理員使用。"

    return (
        "🛠 管理員\n\n"
        "目前管理員權限已由 SERVICE_CENTER_ADMIN_IDS 判斷。\n\n"
        "下一步可以接：\n"
        "- /announce 公告內容\n"
        "- 查看服務中心使用狀態\n"
        "- 管理遊戲 bot 建立流程"
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


def handle_service_center_message(user_id, bot_id, chat_id, user_text, message_id=None):
    """處理服務中心 bot 的文字訊息。"""
    text = _text_id(user_text)

    if text in ["/start", "/menu", "/服務中心", "/help", "/manual", "/說明"]:
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

    # 第一階段先不把未知文字丟去任何主流程，避免誤進主遊戲或 Gemini。
    send_message(
        chat_id=chat_id,
        text="這裡是 Telemini 服務中心。請使用 /menu 開啟服務選單。",
        reply_markup=_main_menu_markup(user_id),
    )
    return True


def handle_service_center_callback(user_id, bot_id, chat_id, message_id, callback_data, callback_id=None):
    """處理服務中心 bot 的 inline button。"""
    action = _text_id(callback_data)

    if callback_id:
        answer_callback_query(callback_id)

    if not action.startswith("svc:"):
        return True

    if action == "svc:home":
        edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_home_text(),
            reply_markup=_main_menu_markup(user_id),
        )
        return True

    edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=_text_by_action(action, user_id=user_id),
        reply_markup=_back_menu_markup(),
    )
    return True
