import secrets
import threading
import time

from config import (
    GEMINI_MODEL,
    GEMINI_VISION_MODEL,
    GEMINI_VISION_MAX_OUTPUT_TOKENS,
    GEMINI_STICKER_MAX_OUTPUT_TOKENS,
)
from services.bot_router import get_bot_token
from services.call_ai import run_ai
from services.gemini_service import ask_gemini_image_to_text
from services.telegram_service import download_file_bytes, send_message
from services.user_router import get_gemini_key


UNSUPPORTED_MEDIA_TEXT = "程式尚不能對語音、動態貼圖、影片產生回覆"
IMAGE_PARSE_LIMIT_EXCEEDED_TEXT = "不小心超過單次最大限制，消耗圖片次數1次，文字回應一併停止"
IMAGE_PARSE_QUOTA_EXHAUSTED_TEXT = "今日圖片解析次數已用完，文字回應一併停止，請明天再試。"
IMAGE_PARSE_UNAVAILABLE_TEXT = "圖片解析模型目前忙碌中，文字回應一併停止，請稍後再試。"
STICKER_PARSE_LIMIT_EXCEEDED_TEXT = "不小心超過單次最大限制，消耗貼圖次數1次，文字回應一併停止"
STICKER_PARSE_QUOTA_EXHAUSTED_TEXT = "今日貼圖解析次數已用完，文字回應一併停止，請明天再試。"
STICKER_PARSE_UNAVAILABLE_TEXT = "貼圖解析模型目前忙碌中，文字回應一併停止，請稍後再試。"

PHOTO_TEXT_WAIT_SECONDS = 10

# 圖片等待狀態只存在目前 Render process 記憶體。
# key 加入 user_id，避免群組內不同使用者的圖片與文字互相合併。
_PENDING_PHOTOS = {}
_PENDING_PHOTOS_LOCK = threading.Lock()


# =========================
# 共用工具
# =========================
def _text(value):
    return str(value or "").strip()


def _pending_photo_key(user_id, bot_id, chat_id):
    return (_text(user_id), _text(bot_id), _text(chat_id))


def _cancel_pending_timer(item):
    timer = (item or {}).get("timer")

    if not timer:
        return

    try:
        timer.cancel()
    except Exception:
        pass


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


def _media_parse_failure_text(result, *, media_type="photo"):
    status = _text((result or {}).get("status")) or "error"

    print(
        f"MEDIA PARSE FAILURE media_type={media_type} status={status} "
        f"model={_text((result or {}).get('model')) or '-'} "
        f"finish_reason={_text((result or {}).get('finish_reason')) or '-'}",
        flush=True,
    )

    if status == "blocked":
        return (
            "圖片內容被安全阻擋，無法解析。"
            if media_type == "photo"
            else "貼圖內容被安全阻擋，無法解析。"
        )

    if status == "quota_exhausted":
        return (
            IMAGE_PARSE_QUOTA_EXHAUSTED_TEXT
            if media_type == "photo"
            else STICKER_PARSE_QUOTA_EXHAUSTED_TEXT
        )

    if status == "service_unavailable":
        return (
            IMAGE_PARSE_UNAVAILABLE_TEXT
            if media_type == "photo"
            else STICKER_PARSE_UNAVAILABLE_TEXT
        )

    if status in ["max_tokens_no_response", "no_response"]:
        return (
            IMAGE_PARSE_LIMIT_EXCEEDED_TEXT
            if media_type == "photo"
            else STICKER_PARSE_LIMIT_EXCEEDED_TEXT
        )

    return (
        "圖片解析失敗，文字回應一併停止，請稍後再試。"
        if media_type == "photo"
        else "貼圖解析失敗，文字回應一併停止，請稍後再試。"
    )


def _normalize_parse_result(result):
    """相容結構化新版與部署期間可能殘留的舊字串回傳。"""
    if isinstance(result, dict):
        return result

    text = _text(result)

    if text:
        return {
            "ok": True,
            "status": "ok",
            "text": text,
            "model": "",
            "finish_reason": "",
        }

    return {
        "ok": False,
        "status": "no_response",
        "text": "",
        "model": "",
        "finish_reason": "",
    }


# =========================
# 圖片等待狀態
# =========================
def _register_pending_photo(user_id, bot_id, chat_id, message_id=None, caption=""):
    key = _pending_photo_key(user_id, bot_id, chat_id)
    token = secrets.token_urlsafe(12)

    item = {
        "token": token,
        "user_id": user_id,
        "bot_id": bot_id,
        "chat_id": chat_id,
        "image_message_id": message_id,
        "text_message_id": None,
        "caption": _text(caption),
        "texts": [],
        "description": "",
        "model": "",
        "phase": "parsing",
        "timer": None,
        "created_at": time.time(),
        "dispatched": False,
    }

    with _PENDING_PHOTOS_LOCK:
        previous = _PENDING_PHOTOS.pop(key, None)

        if previous:
            _cancel_pending_timer(previous)
            previous["superseded"] = True

        _PENDING_PHOTOS[key] = item

    print(
        "MEDIA PHOTO PENDING CREATED "
        f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
        f"message_id={message_id} wait_seconds={PHOTO_TEXT_WAIT_SECONDS} "
        f"replaced_previous={bool(previous)}",
        flush=True,
    )

    return token


def _build_photo_user_text(description, caption="", texts=None, model=""):
    texts = [value for value in (texts or []) if _text(value)]
    model_name = _text(model) or "Gemini 圖片模型"

    sections = [
        "【使用者傳送了一張圖片】",
        f"【{model_name} 圖片解析結果】",
        _text(description),
    ]

    if _text(caption):
        sections.extend([
            "【圖片原始附註】",
            _text(caption),
        ])

    if texts:
        sections.extend([
            "【使用者在圖片後補充的訊息】",
            "\n".join(texts),
        ])

    sections.append(
        "請把圖片、圖片附註與補充訊息視為同一次使用者輸入，"
        "依照目前對話脈絡、角色設定與原本語氣自然回覆。"
    )

    return "\n".join(section for section in sections if section)


def _dispatch_photo_item(item, reason):
    if not item or item.get("dispatched"):
        return False

    item["dispatched"] = True
    _cancel_pending_timer(item)

    description = _text(item.get("description"))
    texts = list(item.get("texts") or [])
    caption = _text(item.get("caption"))

    if not description:
        return False

    synthetic_text = _build_photo_user_text(
        description=description,
        caption=caption,
        texts=texts,
        model=item.get("model"),
    )

    source_message_id = item.get("text_message_id") or item.get("image_message_id")

    print(
        "MEDIA PHOTO DISPATCH "
        f"reason={reason} user_id={item.get('user_id')} "
        f"bot_id={item.get('bot_id')} chat_id={item.get('chat_id')} "
        f"caption={bool(caption)} buffered_text_count={len(texts)} "
        f"combined_len={len(synthetic_text)}",
        flush=True,
    )

    run_ai(
        user_id=item.get("user_id"),
        bot_id=item.get("bot_id"),
        chat_id=item.get("chat_id"),
        user_text=synthetic_text,
        user_message_id=source_message_id,
    )
    return True


def _remove_pending_photo(key, token):
    with _PENDING_PHOTOS_LOCK:
        current = _PENDING_PHOTOS.get(key)

        if not current or current.get("token") != token:
            return None

        return _PENDING_PHOTOS.pop(key, None)


def _fail_pending_photo(user_id, bot_id, chat_id, token, failure_text):
    """
    圖片解析失敗時，清除等待狀態並只送失敗提示。

    解析期間被緩衝的文字也直接中斷，不另行呼叫文字模型，
    符合「文字回應一併停止」規則。
    """
    key = _pending_photo_key(user_id, bot_id, chat_id)
    item = _remove_pending_photo(key, token) if token else None

    if item:
        _cancel_pending_timer(item)
        print(
            "MEDIA PHOTO PENDING FAILED "
            f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
            f"buffered_text_discarded={len(item.get('texts') or [])}",
            flush=True,
        )

    send_message(bot_id, chat_id, failure_text)


def _photo_wait_timeout(key, token):
    item = None

    with _PENDING_PHOTOS_LOCK:
        current = _PENDING_PHOTOS.get(key)

        if not current or current.get("token") != token:
            return

        if current.get("phase") != "waiting":
            return

        item = _PENDING_PHOTOS.pop(key, None)

    if item:
        print(
            "MEDIA PHOTO WAIT TIMEOUT "
            f"user_id={item.get('user_id')} chat_id={item.get('chat_id')} "
            f"wait_seconds={PHOTO_TEXT_WAIT_SECONDS}",
            flush=True,
        )
        _dispatch_photo_item(item, reason="wait_timeout")


def _complete_pending_photo(user_id, bot_id, chat_id, token, description, model=""):
    key = _pending_photo_key(user_id, bot_id, chat_id)
    dispatch_now = None
    timer_to_start = None

    with _PENDING_PHOTOS_LOCK:
        current = _PENDING_PHOTOS.get(key)

        if not current or current.get("token") != token:
            return False

        current["description"] = _text(description)
        current["model"] = _text(model)
        current["phase"] = "waiting"

        if current.get("texts"):
            dispatch_now = _PENDING_PHOTOS.pop(key, None)
        else:
            timer = threading.Timer(
                PHOTO_TEXT_WAIT_SECONDS,
                _photo_wait_timeout,
                args=(key, token),
            )
            timer.daemon = True
            current["timer"] = timer
            timer_to_start = timer

    if dispatch_now:
        print(
            "MEDIA PHOTO PARSE COMPLETE WITH BUFFERED TEXT "
            f"user_id={user_id} chat_id={chat_id} "
            f"buffered_text_count={len(dispatch_now.get('texts') or [])}",
            flush=True,
        )
        _dispatch_photo_item(dispatch_now, reason="text_arrived_during_parsing")
        return True

    if timer_to_start:
        print(
            "MEDIA PHOTO WAIT START "
            f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
            f"wait_seconds={PHOTO_TEXT_WAIT_SECONDS}",
            flush=True,
        )
        timer_to_start.start()
        return True

    return False


def queue_text_for_pending_photo(user_id, bot_id, chat_id, user_text, message_id=None):
    """
    一般文字進入 run_ai 前先呼叫。

    回傳 True：文字已被圖片等待器接收，不可再走一般文字回覆。
    回傳 False：目前沒有待處理圖片，照原本流程處理。
    """
    text = _text(user_text)

    if not text:
        return False

    key = _pending_photo_key(user_id, bot_id, chat_id)
    dispatch_now = None
    phase = ""

    with _PENDING_PHOTOS_LOCK:
        current = _PENDING_PHOTOS.get(key)

        if not current:
            return False

        phase = current.get("phase") or "parsing"
        current.setdefault("texts", []).append(text)
        current["text_message_id"] = message_id

        if phase == "waiting" and current.get("description"):
            _cancel_pending_timer(current)
            dispatch_now = _PENDING_PHOTOS.pop(key, None)

    print(
        "MEDIA PHOTO TEXT BUFFERED "
        f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
        f"phase={phase} text_len={len(text)} dispatch_now={bool(dispatch_now)}",
        flush=True,
    )

    if dispatch_now:
        print(
            "MEDIA PHOTO WAIT CANCEL reason=text_received "
            f"user_id={user_id} chat_id={chat_id}",
            flush=True,
        )
        _dispatch_photo_item(dispatch_now, reason="text_received")

    return True


# =========================
# 圖片分流：3.5 Flash 讀圖 → 等待 10 秒 → 3.1 Flash Lite 回覆
# =========================
def handle_photo_message(user_id, bot_id, chat_id, message, message_id=None, pending_token=None):
    gemini_key = get_gemini_key(user_id)
    bot_token = get_bot_token(bot_id)

    if not gemini_key or not bot_token:
        failure_text = "圖片處理需要先完成 Bot 與 Gemini API 設定。"

        if pending_token:
            _fail_pending_photo(user_id, bot_id, chat_id, pending_token, failure_text)
        else:
            _missing_config(bot_id, chat_id, user_id)
        return

    photos = message.get("photo") or []

    if not photos:
        _fail_pending_photo(
            user_id,
            bot_id,
            chat_id,
            pending_token,
            "圖片讀取失敗，文字回應一併停止，請再傳一次。",
        )
        return

    # Telegram photo 由小到大排序，最後一張通常最大。
    photo = photos[-1] or {}
    file_id = photo.get("file_id")
    caption = _text(message.get("caption"))

    print(
        "MEDIA PHOTO PARSE START "
        f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
        f"message_id={message_id} model={GEMINI_VISION_MODEL} "
        f"caption={bool(caption)} max_output_tokens={GEMINI_VISION_MAX_OUTPUT_TOKENS}",
        flush=True,
    )

    media = _download_image(bot_id, file_id)

    if not media:
        _fail_pending_photo(
            user_id,
            bot_id,
            chat_id,
            pending_token,
            "圖片讀取失敗，文字回應一併停止，請再傳一次。",
        )
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

    raw_result = ask_gemini_image_to_text(
        gemini_key=gemini_key,
        image_bytes=media.get("bytes"),
        mime_type=media.get("mime_type"),
        prompt=prompt,
        model=GEMINI_VISION_MODEL,
        temperature=0.1,
        max_output_tokens=GEMINI_VISION_MAX_OUTPUT_TOKENS,
    )
    parse_result = _normalize_parse_result(raw_result)
    description = _text(parse_result.get("text"))

    if not parse_result.get("ok") or not description:
        failure_text = _media_parse_failure_text(parse_result, media_type="photo")
        _fail_pending_photo(
            user_id,
            bot_id,
            chat_id,
            pending_token,
            failure_text,
        )
        return

    print(
        "MEDIA PHOTO PARSE OK "
        f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} "
        f"description_len={len(description)} "
        f"model={_text(parse_result.get('model')) or GEMINI_VISION_MODEL} "
        f"finish_reason={_text(parse_result.get('finish_reason')) or '-'}",
        flush=True,
    )

    if pending_token:
        _complete_pending_photo(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            token=pending_token,
            description=description,
            model=parse_result.get("model"),
        )
        return

    # 相容其他直接呼叫 handle_photo_message 的舊流程。
    fallback_item = {
        "user_id": user_id,
        "bot_id": bot_id,
        "chat_id": chat_id,
        "image_message_id": message_id,
        "text_message_id": None,
        "caption": caption,
        "texts": [],
        "description": description,
        "model": parse_result.get("model"),
    }
    _dispatch_photo_item(fallback_item, reason="legacy_direct_call")


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

    raw_result = ask_gemini_image_to_text(
        gemini_key=gemini_key,
        image_bytes=media.get("bytes"),
        mime_type=media.get("mime_type"),
        prompt=prompt,
        model=GEMINI_MODEL,
        temperature=0.1,
        max_output_tokens=GEMINI_STICKER_MAX_OUTPUT_TOKENS,
    )
    parse_result = _normalize_parse_result(raw_result)
    description = _text(parse_result.get("text"))

    if not parse_result.get("ok") or not description:
        send_message(
            bot_id,
            chat_id,
            _media_parse_failure_text(parse_result, media_type="sticker"),
        )
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
    # 解析 thread 啟動前先建立等待狀態，接住圖片後立刻補送的文字。
    pending_token = _register_pending_photo(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        message_id=message_id,
        caption=_text((message or {}).get("caption")),
    )

    threading.Thread(
        target=handle_photo_message,
        args=(user_id, bot_id, chat_id, message, message_id, pending_token),
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
