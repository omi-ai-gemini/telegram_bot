import threading

from config import GEMINI_MODEL, GEMINI_VISION_MODEL
from services.bot_router import get_bot_token
from services.call_ai import run_ai
from services.gemini_service import GEMINI_BLOCKED, ask_gemini_image_to_text
from services.telegram_service import download_file_bytes, send_message
from services.user_router import get_gemini_key


UNSUPPORTED_MEDIA_TEXT = "程式尚不能對語音、動態貼圖、影片產生回覆"


# =========================
# 共用工具
# =========================
def _text(value):
    return str(value or "").strip()


def _missing_config(bot_id, chat_id, user_id):
    send_message(
        bot_id,
        chat_id,
        f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}",
    )


def send_unsupported_media_message(bot_id, chat_id):
    send_message(bot_id, chat_id, UNSUPPORTED_MEDIA_TEXT)


def _download_image(bot_id, file_id):
    if not file_id:
        return None

    item = download_file_bytes(bot_id, file_id)

    if not item:
        return None

    mime_type = _text(item.get("mime_type")) or "image/jpeg"

    if not mime_type.startswith("image/"):
        print(f"MEDIA DOWNLOAD SKIP non-image mime={mime_type}", flush=True)
        return None

    return item


# =========================
# 圖片分流：photo → 2.5 Flash 讀圖 → 3.1 Flash Lite 回覆
# =========================
def handle_photo_message(user_id, bot_id, chat_id, message, message_id=None):
    gemini_key = get_gemini_key(user_id)
    bot_token = get_bot_token(bot_id)

    if not gemini_key or not bot_token:
        _missing_config(bot_id, chat_id, user_id)
        return

    photos = message.get("photo") or []

    if not photos:
        send_unsupported_media_message(bot_id, chat_id)
        return

    # Telegram photo 由小到大排序，最後一張通常最大。
    photo = photos[-1] or {}
    file_id = photo.get("file_id")
    caption = _text(message.get("caption"))

    media = _download_image(bot_id, file_id)

    if not media:
        send_message(bot_id, chat_id, "圖片讀取失敗，請再傳一次。")
        return

    prompt = f"""
你是圖片解析器，只負責把使用者傳來的圖片轉成可供聊天模型理解的繁體中文描述。

請描述：
1. 圖片主要內容
2. 明顯人物、物品、文字、表情、動作或情境
3. 如果看起來像截圖、梗圖、商品、文件、錯誤畫面，也請指出
4. 不要替使用者延伸目的，不要直接扮演聊天角色

使用者圖片附註：{caption or "無"}
""".strip()

    description = ask_gemini_image_to_text(
        gemini_key=gemini_key,
        image_bytes=media.get("bytes"),
        mime_type=media.get("mime_type"),
        prompt=prompt,
        model=GEMINI_VISION_MODEL,
        temperature=0.1,
        max_output_tokens=700,
    )

    if description == GEMINI_BLOCKED:
        send_message(bot_id, chat_id, "圖片內容被安全阻擋，無法解析。")
        return

    if not description:
        send_message(bot_id, chat_id, "圖片解析失敗，請稍後再試一次。")
        return

    # 讓主聊天模型照原本文字流程回覆，維持「文字回覆交由 3.1」的主架構。
    synthetic_text = (
        "【使用者傳送了一張圖片】\n"
        f"使用者圖片附註：{caption or '無'}\n"
        "Gemini 2.5 Flash 圖片解析：\n"
        f"{description}\n\n"
        "請根據目前對話脈絡，用原本角色與語氣自然回覆使用者。"
    )

    run_ai(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=synthetic_text,
        user_message_id=message_id,
    )


# =========================
# 靜態貼圖：3.1 Flash Lite 讀貼圖 → 3.1 Flash Lite 原聊天流程回覆
# =========================
def handle_sticker_message(user_id, bot_id, chat_id, message, message_id=None):
    sticker = message.get("sticker") or {}

    if sticker.get("is_animated") or sticker.get("is_video"):
        send_unsupported_media_message(bot_id, chat_id)
        return

    gemini_key = get_gemini_key(user_id)
    bot_token = get_bot_token(bot_id)

    if not gemini_key or not bot_token:
        _missing_config(bot_id, chat_id, user_id)
        return

    file_id = sticker.get("file_id")
    emoji = _text(sticker.get("emoji"))
    set_name = _text(sticker.get("set_name"))
    sticker_type = _text(sticker.get("type"))

    media = _download_image(bot_id, file_id)

    if not media:
        send_message(bot_id, chat_id, "貼圖讀取失敗，請再傳一次。")
        return

    prompt = f"""
你是 Telegram 靜態貼圖解析器，只負責把貼圖畫面轉成繁體中文描述。

請描述：
1. 貼圖中的角色、表情、動作、文字或情緒
2. 這張貼圖在聊天中可能代表的語氣，例如吐槽、開心、敷衍、撒嬌、生氣、尷尬
3. 不要直接回覆使用者，只輸出貼圖解析

貼圖關聯 emoji：{emoji or "無"}
貼圖包：{set_name or "無"}
貼圖類型：{sticker_type or "regular"}
""".strip()

    description = ask_gemini_image_to_text(
        gemini_key=gemini_key,
        image_bytes=media.get("bytes"),
        mime_type=media.get("mime_type"),
        prompt=prompt,
        model=GEMINI_MODEL,
        temperature=0.1,
        max_output_tokens=500,
    )

    if description == GEMINI_BLOCKED:
        send_message(bot_id, chat_id, "貼圖內容被安全阻擋，無法解析。")
        return

    if not description:
        send_message(bot_id, chat_id, "貼圖解析失敗，請稍後再試一次。")
        return

    synthetic_text = (
        "【使用者傳送了一張靜態貼圖】\n"
        f"貼圖關聯 emoji：{emoji or '無'}\n"
        f"貼圖解析：{description}\n\n"
        "請依照目前對話脈絡，把這張貼圖視為使用者剛剛的回應，"
        "用原本角色與語氣自然接話。"
    )

    run_ai(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        user_text=synthetic_text,
        user_message_id=message_id,
    )


# =========================
# Webhook 背景入口
# =========================
def run_photo_message_in_thread(user_id, bot_id, chat_id, message, message_id=None):
    threading.Thread(
        target=handle_photo_message,
        args=(user_id, bot_id, chat_id, message, message_id),
        daemon=True,
    ).start()


def run_sticker_message_in_thread(user_id, bot_id, chat_id, message, message_id=None):
    threading.Thread(
        target=handle_sticker_message,
        args=(user_id, bot_id, chat_id, message, message_id),
        daemon=True,
    ).start()


def run_unsupported_media_in_thread(bot_id, chat_id):
    threading.Thread(
        target=send_unsupported_media_message,
        args=(bot_id, chat_id),
        daemon=True,
    ).start()
