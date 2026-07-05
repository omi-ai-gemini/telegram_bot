from datetime import datetime, timedelta
import os
import secrets
import threading
import time

from services.bot_router import get_bot_token
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.database import get_conn
from services.gemini_service import GEMINI_BLOCKED, ask_gemini
from services.memory import (
    add_chat,
    get_chat,
    get_chat_memory_item,
    get_chat_until,
    get_facts,
    update_chat_text,
    update_emotion,
    detect_emotion,
    get_emotion,
)
from services.memory_summary import get_memory_context, maintain_memory_after_reply
from services.reply_style import get_reply_style_settings
from services.telegram_service import delete_message, edit_message_text, send_message
from services.time_context import get_current_time_context
from services.user_router import get_gemini_key


EDIT_PENDING_MINUTES = 5
THOUGHT_CACHE_TTL_SECONDS = 60 * 60
CONTINUE_USER_TEXT = """
【接續劇情指令】
這不是新的使用者對話，也不是重新回答上一句。
這是使用者按下「接續」功能後送進來的控制指令。

請把目前短期記憶中的最後一則 AI 回覆，視為剛剛才發生的上一幕，
從那一幕的下一秒自然接下去。

接續要求：
1. 必須承接上一句的情緒、動作、場景、語氣與人物狀態。
2. 必須有新的劇情推進，可以是新的反應、動作、對話轉折、情緒變化或事件線索。
3. 不要重述上一則回覆，不要改寫上一則回覆，不要整理上一則回覆。
4. 不要像重新輸出同一段，不要回到場景開頭，不要重新介紹人物。
5. 不要等待使用者輸入，不要問「要不要繼續」。
6. 不要替使用者說話、行動或決定想法。
7. 如果是聊天模式，就自然補上下一句；如果是劇場模式，就自然推進下一幕。

請直接輸出接續內容。
"""


# =========================
# Gemini 推理摘要暫存
# =========================
# 只放 Render 記憶體：
# - 不寫 DB
# - 不寫檔案
# - Render 重啟會消失
# - 超過 THOUGHT_CACHE_TTL_SECONDS 自動視為過期
#
# action_id 用在 Telegram 訊息操作按鈕。
# token 用在網頁網址，避免 action_id 直接裸露或被猜。
_THOUGHT_CACHE = {}
_THOUGHT_TOKEN_INDEX = {}
_THOUGHT_CACHE_LOCK = threading.Lock()


def _text_id(value):
    return str(value or "").strip()


def _is_group_chat(chat_id):
    try:
        return int(chat_id) < 0
    except Exception:
        return str(chat_id).startswith("-")


def _should_show_ai_buttons_for_mode(mode):
    """
    聊天模式預設隱藏 AI 操作按鈕。

    目的：
    - 一般聊天看起來像正常真人對話，不露出開發者功能。
    - 劇場模式保留原本訊息下方操作按鈕。
    - 聊天模式需要操作時，改由 /hidden 叫出一層開發者按鈕。
    """
    return str(mode or "聊天模式").strip() != "聊天模式"


def _should_show_ai_buttons(user_id, bot_id, chat_id):
    try:
        settings = get_character_settings(bot_id, chat_id, user_id=user_id)
        return _should_show_ai_buttons_for_mode(settings.get("mode", "聊天模式"))
    except Exception as exc:
        print("AI BUTTON MODE CHECK ERROR:", exc, flush=True)
        return False


def _hidden_reply_markup(action_id):
    if not action_id:
        return None
    return build_ai_action_keyboard(action_id)


def _purge_expired_thought_cache(now=None):
    now = now or time.time()

    expired_action_ids = [
        action_id
        for action_id, item in _THOUGHT_CACHE.items()
        if item.get("expires_at", 0) <= now
    ]

    for action_id in expired_action_ids:
        item = _THOUGHT_CACHE.pop(action_id, None) or {}
        token = item.get("token")
        if token:
            _THOUGHT_TOKEN_INDEX.pop(token, None)


def _get_or_create_ai_thought_token(action_id):
    """
    取得某則 AI 回覆的推理摘要網頁 token。

    token 只存在 Render 記憶體，不寫 DB。
    build keyboard 時會先建立 token，cache thought 時再補上文字。
    """
    if not action_id:
        return ""

    action_id = str(action_id)
    now = time.time()

    with _THOUGHT_CACHE_LOCK:
        _purge_expired_thought_cache(now)

        item = _THOUGHT_CACHE.get(action_id)
        if item and item.get("token"):
            item["expires_at"] = now + THOUGHT_CACHE_TTL_SECONDS
            return item.get("token")

        token = secrets.token_urlsafe(32)

        _THOUGHT_CACHE[action_id] = {
            "token": token,
            "text": "",
            "status": "pending",
            "reason": "推理摘要尚未寫入快取。",
            "created_at": now,
            "expires_at": now + THOUGHT_CACHE_TTL_SECONDS,
            "pid": os.getpid(),
        }
        _THOUGHT_TOKEN_INDEX[token] = action_id

        print(
            f"THOUGHT token created action_id={action_id} "
            f"token={token[:8]} pid={os.getpid()}",
            flush=True
        )

        return token


def get_ai_thought_url(action_id):
    """
    建立 🧠 按鈕用的網頁網址。

    需要 Render 設定 BASE_URL。
    沒有 BASE_URL 時回傳 None，讓按鈕退回 callback 提示。
    """
    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url or not action_id:
        return None

    token = _get_or_create_ai_thought_token(action_id)

    if not token:
        return None

    return f"{base_url}/thought/{token}"


def build_ai_action_keyboard(action_id):
    thought_url = get_ai_thought_url(action_id)

    thought_button = (
        {"text": "🧠", "url": thought_url}
        if thought_url
        else {"text": "🧠", "callback_data": f"ai_thought_missing:{action_id}"}
    )

    return {
        "inline_keyboard": [[
            {"text": "🗣️", "callback_data": f"ai_reply:{action_id}"},
            {"text": "✏️", "callback_data": f"ai_edit:{action_id}"},
            {"text": "🔁", "callback_data": f"ai_regen:{action_id}"},
            thought_button,
            {"text": "▶️", "callback_data": f"ai_continue:{action_id}"},
        ]]
    }


def _get_latest_ai_action_id(bot_id, chat_id, user_id):
    """取得目前聊天室最後一筆可操作的 AI action。"""
    if _is_group_chat(chat_id):
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id
            FROM ai_message_actions
            WHERE bot_id = %s
              AND chat_id = %s
              AND user_id = %s
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        """, (
            _text_id(bot_id),
            _text_id(chat_id),
            _text_id(user_id),
        ))

        row = cursor.fetchone()
        return int(row[0]) if row else None

    except Exception as exc:
        print("DB ERROR get_latest_ai_action_id:", exc, flush=True)
        return None

    finally:
        conn.close()


def _create_latest_hidden_action_from_memory(bot_id, chat_id, user_id):
    """
    舊資料相容用。

    如果聊天室已經有 AI 記憶，但還沒有 ai_message_actions，
    /hidden 仍嘗試為最近一筆 assistant 建立 action。
    這種舊 action 可能沒有 telegram_message_id，所以「✏️ / 🔁」可能無法操作舊訊息，
    但「🗣️ / 🧠 / ▶️」仍有機會使用。
    """
    if _is_group_chat(chat_id):
        return None

    scope = "group" if _is_group_chat(chat_id) else "private"
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, role
            FROM chat_memory
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id DESC
            LIMIT 30
        """, (
            _text_id(bot_id),
            _text_id(chat_id),
            scope,
        ))

        rows = cursor.fetchall()
        assistant_chat_id = None
        source_user_chat_id = None

        for row_id, role in rows:
            role = str(role or "").strip()

            if assistant_chat_id is None and role == "assistant":
                assistant_chat_id = int(row_id)
                continue

            if assistant_chat_id is not None and role == "user":
                source_user_chat_id = int(row_id)
                break

        if not assistant_chat_id:
            return None

        action_id = create_ai_message_action(
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            assistant_chat_id=assistant_chat_id,
            source_user_chat_id=source_user_chat_id,
            context_chat_id=source_user_chat_id,
            generation_type="hidden_latest",
        )

        if action_id:
            cache_ai_thought_summary(action_id, "", status="empty")

        return action_id

    except Exception as exc:
        print("DB ERROR create_latest_hidden_action_from_memory:", exc, flush=True)
        return None

    finally:
        conn.close()


def send_hidden_ai_action_menu(bot_id, chat_id, user_id):
    """
    /hidden 開發者功能選單。

    聊天模式預設不在 AI 訊息下方顯示任何特殊按鈕，
    只有使用者手動輸入 /hidden 時，才顯示一層操作按鈕。
    """
    if _is_group_chat(chat_id):
        send_message(bot_id, chat_id, "群組暫不開放 /hidden 開發者功能")
        return False

    action_id = _get_latest_ai_action_id(bot_id, chat_id, user_id)

    if not action_id:
        action_id = _create_latest_hidden_action_from_memory(bot_id, chat_id, user_id)

    if not action_id:
        send_message(bot_id, chat_id, "目前沒有可操作的 AI 回覆")
        return False

    reply_markup = _hidden_reply_markup(action_id)

    send_message(
        bot_id,
        chat_id,
        "開發者功能｜選擇要操作的最近一則 AI 回覆",
        reply_markup=reply_markup,
    )

    print(
        f"HIDDEN MENU SENT action_id={action_id} bot_id={bot_id} chat_id={chat_id}",
        flush=True,
    )

    return True


def cache_ai_thought_summary(action_id, thought_text, status=None, reason=None):
    """
    暫存 🧠 回覆依據。

    不保存到資料庫；只讓 🧠 網頁短時間內可查看。

    status：
    - official：Gemini API 回傳的 thought summary。
    - generated：同次 JSON 輸出的 reasoning_note。
    - empty：本次沒有可顯示內容。
    """
    if not action_id:
        return False

    thought_text = str(thought_text or "").strip()
    action_id = str(action_id)
    now = time.time()

    status = str(status or "").strip()

    if status not in ["official", "generated", "empty"]:
        status = "generated" if thought_text else "empty"

    if not thought_text:
        status = "empty"

    if reason is None:
        if status == "official":
            reason = "這是 Gemini API 回傳的 thought summary，不是完整逐字內部推理。"
        elif status == "generated":
            reason = "這是 Gemini 同次輸出的回覆依據摘要，不代表完整內部推理。"
        else:
            reason = "Gemini 這次沒有提供可顯示的 thought summary 或 reasoning_note。"

    with _THOUGHT_CACHE_LOCK:
        _purge_expired_thought_cache(now)

        item = _THOUGHT_CACHE.get(action_id) or {}
        token = item.get("token")

        if not token:
            token = secrets.token_urlsafe(32)
            _THOUGHT_TOKEN_INDEX[token] = action_id

        _THOUGHT_CACHE[action_id] = {
            "token": token,
            "text": thought_text,
            "status": status,
            "reason": str(reason or ""),
            "created_at": item.get("created_at") or now,
            "expires_at": now + THOUGHT_CACHE_TTL_SECONDS,
            "pid": os.getpid(),
        }
        _THOUGHT_TOKEN_INDEX[token] = action_id

    print(
        f"THOUGHT cache saved action_id={action_id} token={token[:8]} "
        f"status={status} len={len(thought_text)} pid={os.getpid()}",
        flush=True
    )

    return True


def clear_ai_thought_summary(action_id):
    if not action_id:
        return

    with _THOUGHT_CACHE_LOCK:
        item = _THOUGHT_CACHE.pop(str(action_id), None) or {}
        token = item.get("token")
        if token:
            _THOUGHT_TOKEN_INDEX.pop(token, None)


def get_ai_thought_summary_by_token(token):
    """
    推理摘要網頁讀取入口。

    回傳 None 代表：
    - token 不存在
    - Render 重啟後記憶體消失
    - 快取已過期
    """
    token = str(token or "").strip()

    if not token:
        return None

    now = time.time()

    with _THOUGHT_CACHE_LOCK:
        _purge_expired_thought_cache(now)

        action_id = _THOUGHT_TOKEN_INDEX.get(token)

        if not action_id:
            print(
                f"THOUGHT cache miss token={token[:8]} pid={os.getpid()}",
                flush=True
            )
            return None

        item = _THOUGHT_CACHE.get(action_id)

        if not item:
            _THOUGHT_TOKEN_INDEX.pop(token, None)
            print(
                f"THOUGHT cache index stale token={token[:8]} action_id={action_id} pid={os.getpid()}",
                flush=True
            )
            return None

        if item.get("expires_at", 0) <= now:
            _THOUGHT_CACHE.pop(action_id, None)
            _THOUGHT_TOKEN_INDEX.pop(token, None)
            print(
                f"THOUGHT cache expired token={token[:8]} action_id={action_id} pid={os.getpid()}",
                flush=True
            )
            return None

        text = str(item.get("text") or "").strip()
        status = str(item.get("status") or ("ready" if text else "empty")).strip()
        reason = str(item.get("reason") or "").strip()

        print(
            f"THOUGHT cache hit token={token[:8]} action_id={action_id} "
            f"status={status} len={len(text)} save_pid={item.get('pid')} read_pid={os.getpid()}",
            flush=True
        )

        return {
            "action_id": action_id,
            "text": text,
            "status": status,
            "reason": reason,
            "created_at": item.get("created_at"),
            "expires_at": item.get("expires_at"),
            "pid": item.get("pid"),
        }


def _split_gemini_result(result):
    """
    相容舊回傳字串與新回傳 dict。

    回傳：
    - reply：正式回覆
    - thought_summary：🧠 要顯示的回覆依據
    - thought_source：official / generated / empty
    """
    if isinstance(result, dict):
        return (
            result.get("text"),
            result.get("thoughts", ""),
            result.get("thought_source", "empty"),
        )

    return result, "", "empty"

def create_ai_message_action(
    bot_id,
    chat_id,
    user_id,
    assistant_chat_id,
    source_user_chat_id=None,
    context_chat_id=None,
    generation_type="reply",
):
    """建立 AI 訊息與 Telegram 訊息按鈕的對應資料，回傳 action_id。"""
    if _is_group_chat(chat_id):
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_message_actions (
                bot_id,
                chat_id,
                user_id,
                assistant_chat_id,
                source_user_chat_id,
                context_chat_id,
                generation_type,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (
            _text_id(bot_id),
            _text_id(chat_id),
            _text_id(user_id),
            int(assistant_chat_id),
            source_user_chat_id,
            context_chat_id,
            generation_type,
        ))

        row = cursor.fetchone()
        conn.commit()
        return int(row[0]) if row else None

    except Exception as exc:
        conn.rollback()
        print("DB ERROR create_ai_message_action:", exc)
        return None

    finally:
        conn.close()


def update_action_telegram_message_id(action_id, telegram_message_id):
    if not action_id or not telegram_message_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ai_message_actions
            SET telegram_message_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(telegram_message_id), int(action_id)))

        ok = cursor.rowcount > 0
        conn.commit()
        return ok

    except Exception as exc:
        conn.rollback()
        print("DB ERROR update_action_telegram_message_id:", exc)
        return False

    finally:
        conn.close()


def get_ai_message_action(action_id, bot_id, chat_id, user_id=None):
    try:
        action_id = int(action_id)
    except Exception:
        return None

    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    user_id = None if user_id is None else _text_id(user_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        params = [action_id, bot_id, chat_id]
        user_sql = ""

        if user_id:
            user_sql = "AND user_id = %s"
            params.append(user_id)

        cursor.execute(f"""
            SELECT
                id,
                bot_id,
                chat_id,
                user_id,
                telegram_message_id,
                assistant_chat_id,
                source_user_chat_id,
                context_chat_id,
                generation_type
            FROM ai_message_actions
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              {user_sql}
        """, params)

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "bot_id": row[1],
            "chat_id": row[2],
            "user_id": row[3],
            "telegram_message_id": row[4],
            "assistant_chat_id": row[5],
            "source_user_chat_id": row[6],
            "context_chat_id": row[7],
            "generation_type": row[8] or "reply",
        }

    except Exception as exc:
        print("DB ERROR get_ai_message_action:", exc)
        return None

    finally:
        conn.close()


def create_pending_edit(bot_id, chat_id, user_id, target_action_id, prompt_message_id):
    expires_at = datetime.utcnow() + timedelta(minutes=EDIT_PENDING_MINUTES)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        # 同一個 user / chat 同時間只保留一個待修改狀態。
        cursor.execute("""
            DELETE FROM pending_ai_actions
            WHERE bot_id = %s
              AND chat_id = %s
              AND user_id = %s
              AND action_type = 'edit_ai_message'
        """, (_text_id(bot_id), _text_id(chat_id), _text_id(user_id)))

        cursor.execute("""
            INSERT INTO pending_ai_actions (
                bot_id,
                chat_id,
                user_id,
                action_type,
                target_action_id,
                prompt_message_id,
                expires_at
            )
            VALUES (%s, %s, %s, 'edit_ai_message', %s, %s, %s)
        """, (
            _text_id(bot_id),
            _text_id(chat_id),
            _text_id(user_id),
            int(target_action_id),
            prompt_message_id,
            expires_at,
        ))

        conn.commit()
        return True

    except Exception as exc:
        conn.rollback()
        print("DB ERROR create_pending_edit:", exc)
        return False

    finally:
        conn.close()


def pop_active_pending_edit(bot_id, chat_id, user_id):
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, target_action_id, prompt_message_id, expires_at
            FROM pending_ai_actions
            WHERE bot_id = %s
              AND chat_id = %s
              AND user_id = %s
              AND action_type = 'edit_ai_message'
            ORDER BY created_at DESC
            LIMIT 1
        """, (_text_id(bot_id), _text_id(chat_id), _text_id(user_id)))

        row = cursor.fetchone()

        if not row:
            return None

        pending_id, target_action_id, prompt_message_id, expires_at = row

        # 無論有效或過期，取出後都清掉，避免下一句又被攔截。
        cursor.execute("""
            DELETE FROM pending_ai_actions
            WHERE id = %s
        """, (pending_id,))

        conn.commit()

        if expires_at and expires_at < datetime.utcnow():
            return {
                "expired": True,
                "prompt_message_id": prompt_message_id,
            }

        return {
            "expired": False,
            "target_action_id": target_action_id,
            "prompt_message_id": prompt_message_id,
        }

    except Exception as exc:
        conn.rollback()
        print("DB ERROR pop_active_pending_edit:", exc)
        return None

    finally:
        conn.close()


def _extract_telegram_message_id(result):
    if not isinstance(result, dict):
        return None

    message = result.get("result") or {}
    return message.get("message_id")


def start_edit_ai_message(user_id, bot_id, chat_id, action_id):
    if _is_group_chat(chat_id):
        return False, "群組暫不開放這個功能"

    action = get_ai_message_action(action_id, bot_id, chat_id, user_id=user_id)

    if not action or not action.get("telegram_message_id"):
        return False, "這則回覆已無法操作"

    prompt = send_message(
        bot_id,
        chat_id,
        "請輸入要替換成的新內容，送出後我會自動刪除這則提示跟你的修改稿。"
    )
    prompt_message_id = _extract_telegram_message_id(prompt)

    ok = create_pending_edit(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        target_action_id=action_id,
        prompt_message_id=prompt_message_id,
    )

    if not ok:
        return False, "建立修改狀態失敗"

    return True, "請輸入修改後文字"


def process_pending_edit_message(user_id, bot_id, chat_id, user_text, user_message_id=None):
    """
    如果目前有待修改狀態，攔截使用者下一句文字：
    - 不送 Gemini
    - 不寫入 user chat_memory
    - 編輯原 AI 訊息
    - 更新原 assistant chat_memory
    - 刪除提示訊息與使用者修改稿
    """
    pending = pop_active_pending_edit(bot_id, chat_id, user_id)

    if not pending:
        return False

    if pending.get("prompt_message_id"):
        delete_message(bot_id, chat_id, pending.get("prompt_message_id"))

    if user_message_id:
        delete_message(bot_id, chat_id, user_message_id)

    if pending.get("expired"):
        send_message(bot_id, chat_id, "修改時間已過期，請重新按一次「✏️改」。")
        return True

    action = get_ai_message_action(
        pending.get("target_action_id"),
        bot_id,
        chat_id,
        user_id=user_id,
    )

    if not action or not action.get("telegram_message_id"):
        send_message(bot_id, chat_id, "這則回覆已無法操作")
        return True

    text = str(user_text or "").strip()

    if not text:
        send_message(bot_id, chat_id, "修改內容是空的，已取消。")
        return True

    keyboard = (
        build_ai_action_keyboard(action.get("id"))
        if _should_show_ai_buttons(user_id, bot_id, chat_id)
        else None
    )

    edit_message_text(
        bot_id,
        chat_id,
        action.get("telegram_message_id"),
        text,
        reply_markup=keyboard,
    )

    update_chat_text(
        memory_id=action.get("assistant_chat_id"),
        bot_id=bot_id,
        chat_id=chat_id,
        role="assistant",
        text=text,
    )

    # 使用者手動改掉 AI 回覆後，原本的推理摘要已經不再對應這則文字。
    clear_ai_thought_summary(action.get("id"))

    return True


def _load_generation_context(user_id, bot_id, chat_id):
    gemini_key = get_gemini_key(user_id)
    bot_token = get_bot_token(bot_id)

    if not gemini_key or not bot_token:
        return None

    scope = "group" if _is_group_chat(chat_id) else "private"
    emotion = get_emotion(chat_id)
    facts = get_facts(bot_id, chat_id, scope, user_id=user_id, limit=20)
    memory_context = get_memory_context(bot_id, chat_id, scope, user_id=user_id)
    character_settings = get_character_settings(bot_id, chat_id, user_id=user_id)
    mode = character_settings.get("mode", "聊天模式")
    chat_persona_settings = None

    if mode == "聊天模式":
        chat_persona_settings = get_chat_persona_settings(bot_id, chat_id, user_id=user_id)

    reply_style_settings = get_reply_style_settings(
        bot_id=bot_id,
        chat_id=chat_id,
        style_type=mode,
        user_id=user_id,
    )

    return {
        "gemini_key": gemini_key,
        "scope": scope,
        "emotion": emotion,
        "facts": facts,
        "memory_context": memory_context,
        "character_settings": character_settings,
        "mode": mode,
        "chat_persona_settings": chat_persona_settings,
        "reply_style_settings": reply_style_settings,
        "time_context": get_current_time_context(),
    }


def _generate_reply(context, history, user_text, include_thoughts=True):
    return ask_gemini(
        gemini_key=context["gemini_key"],
        history=history,
        user_text=user_text,
        emotion=context["emotion"],
        mode=context["mode"],
        chat_persona_settings=context["chat_persona_settings"],
        character_settings=context["character_settings"],
        reply_style_settings=context["reply_style_settings"],
        facts=context["facts"],
        memory_context=context["memory_context"],
        time_context=context["time_context"],
        include_thoughts=include_thoughts,
        return_meta=include_thoughts,
    )


def regenerate_ai_message(user_id, bot_id, chat_id, action_id):
    if _is_group_chat(chat_id):
        send_message(bot_id, chat_id, "群組暫不開放這個功能")
        return

    action = get_ai_message_action(action_id, bot_id, chat_id, user_id=user_id)

    if not action or not action.get("telegram_message_id"):
        send_message(bot_id, chat_id, "這則回覆已無法操作")
        return

    # 使用者要求：按下重跑後先把原本那則 AI 訊息刪掉，
    # 等新回覆生成完再重新發一則新的，並更新 action 對應的 telegram_message_id。
    old_telegram_message_id = action.get("telegram_message_id")
    delete_message(bot_id, chat_id, old_telegram_message_id)

    context = _load_generation_context(user_id, bot_id, chat_id)

    if not context:
        send_message(bot_id, chat_id, f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}")
        return

    generation_type = action.get("generation_type") or "reply"

    if generation_type == "continue":
        context_chat_id = action.get("context_chat_id")
        history = get_chat_until(bot_id, chat_id, context_chat_id, user_id=user_id)
        user_text = CONTINUE_USER_TEXT
    else:
        source_user = get_chat_memory_item(action.get("source_user_chat_id"), bot_id, chat_id)

        if not source_user or source_user.get("role") != "user":
            send_message(bot_id, chat_id, "找不到原本那句使用者訊息，無法重跑")
            return

        history = get_chat_until(bot_id, chat_id, source_user.get("id"), user_id=user_id)
        user_text = source_user.get("text") or ""

    gemini_result = _generate_reply(context, history, user_text, include_thoughts=True)
    reply, thought_summary, thought_source = _split_gemini_result(gemini_result)

    if reply == GEMINI_BLOCKED:
        reply = "內容被安全阻擋"

    if not reply:
        print("AI ACTION REGEN SKIP: empty reply")
        return

    cache_ai_thought_summary(action.get("id"), thought_summary, status=thought_source)

    keyboard = (
        build_ai_action_keyboard(action.get("id"))
        if _should_show_ai_buttons_for_mode(context.get("mode"))
        else None
    )

    sent = send_message(
        bot_id,
        chat_id,
        reply,
        reply_markup=keyboard,
    )

    new_telegram_message_id = _extract_telegram_message_id(sent)

    if new_telegram_message_id:
        update_action_telegram_message_id(action.get("id"), new_telegram_message_id)

    update_chat_text(
        memory_id=action.get("assistant_chat_id"),
        bot_id=bot_id,
        chat_id=chat_id,
        role="assistant",
        text=reply,
    )


def continue_ai_message(user_id, bot_id, chat_id, source_action_id=None):
    if _is_group_chat(chat_id):
        send_message(bot_id, chat_id, "群組暫不開放這個功能")
        return

    context = _load_generation_context(user_id, bot_id, chat_id)

    if not context:
        send_message(bot_id, chat_id, f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}")
        return

    # 用來源 AI 訊息當接續基準；如果找不到來源，就用目前最新短期記憶。
    context_chat_id = None

    if source_action_id:
        source_action = get_ai_message_action(source_action_id, bot_id, chat_id, user_id=user_id)
        if source_action:
            context_chat_id = source_action.get("assistant_chat_id")

    if context_chat_id:
        history = get_chat_until(bot_id, chat_id, context_chat_id, user_id=user_id)
    else:
        history = get_chat(bot_id, chat_id, user_id=user_id)

        # 如果找不到來源 action，就用目前最後一筆記憶 id。
        # 只查 id，不把內容印到 log。
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id
                FROM chat_memory
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND scope = %s
                ORDER BY id DESC
                LIMIT 1
            """, (_text_id(bot_id), _text_id(chat_id), context["scope"]))
            row = cursor.fetchone()
            context_chat_id = int(row[0]) if row else None
        except Exception as exc:
            print("DB ERROR fetch context_chat_id:", exc)
        finally:
            conn.close()

    gemini_result = _generate_reply(context, history, CONTINUE_USER_TEXT, include_thoughts=True)
    reply, thought_summary, thought_source = _split_gemini_result(gemini_result)

    if reply == GEMINI_BLOCKED:
        send_message(bot_id, chat_id, "內容被安全阻擋")
        return

    if not reply:
        print("AI ACTION CONTINUE SKIP: empty reply")
        return

    assistant_chat_id = add_chat(
        bot_id,
        chat_id,
        "assistant",
        reply,
        user_id=user_id,
    )

    action_id = create_ai_message_action(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        assistant_chat_id=assistant_chat_id,
        source_user_chat_id=None,
        context_chat_id=context_chat_id,
        generation_type="continue",
    )

    if action_id:
        cache_ai_thought_summary(action_id, thought_summary, status=thought_source)

    keyboard = (
        build_ai_action_keyboard(action_id)
        if action_id and _should_show_ai_buttons_for_mode(context.get("mode"))
        else None
    )
    sent = send_message(bot_id, chat_id, reply, reply_markup=keyboard)
    telegram_message_id = _extract_telegram_message_id(sent)

    if action_id and telegram_message_id:
        update_action_telegram_message_id(action_id, telegram_message_id)

    maintain_memory_after_reply(context["gemini_key"], bot_id, chat_id, user_id=user_id)



def reply_ai_message(user_id, bot_id, chat_id, action_id):
    """
    🗣️ 補送目前這則 AI 回覆。

    目的：把 /reply 的「重送 AI 回覆」能力做成訊息下方小按鈕。
    行為：
    - 讀取這顆按鈕對應的 assistant chat_memory。
    - 重新送出同一段 AI 文字。
    - 不新增 chat_memory，避免短期記憶膨脹。
    - 重新建立一筆 action，讓新送出的訊息也有完整小按鈕。
    """
    if _is_group_chat(chat_id):
        send_message(bot_id, chat_id, "群組暫不開放這個功能")
        return

    action = get_ai_message_action(action_id, bot_id, chat_id, user_id=user_id)

    if not action:
        send_message(bot_id, chat_id, "這則回覆已無法補送")
        return

    item = get_chat_memory_item(action.get("assistant_chat_id"), bot_id, chat_id)

    if not item or str(item.get("role") or "").strip() != "assistant":
        send_message(bot_id, chat_id, "找不到這則 AI 回覆，無法補送")
        return

    text = str(item.get("text") or "").strip()

    if not text:
        send_message(bot_id, chat_id, "這則 AI 回覆是空的，無法補送")
        return

    new_action_id = create_ai_message_action(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        assistant_chat_id=item.get("id"),
        source_user_chat_id=action.get("source_user_chat_id"),
        context_chat_id=action.get("context_chat_id"),
        generation_type="reply_resend",
    )

    # 如果原 action 的回覆依據還在 Render 記憶體，就複製給新 action。
    # 找不到也沒關係，新訊息的 🧠 會顯示空狀態。
    if new_action_id:
        old_thought = None
        with _THOUGHT_CACHE_LOCK:
            old_thought = dict(_THOUGHT_CACHE.get(str(action.get("id"))) or {})

        if old_thought:
            cache_ai_thought_summary(
                new_action_id,
                old_thought.get("text", ""),
                status=old_thought.get("status"),
                reason=old_thought.get("reason"),
            )
        else:
            cache_ai_thought_summary(new_action_id, "", status="empty")

    keyboard = (
        build_ai_action_keyboard(new_action_id)
        if new_action_id and _should_show_ai_buttons(user_id, bot_id, chat_id)
        else None
    )

    print(
        f"AI REPLY BUTTON RESEND START source_action_id={action_id} new_action_id={new_action_id} len={len(text)}",
        flush=True,
    )

    sent = send_message(
        bot_id,
        chat_id,
        text,
        reply_markup=keyboard,
    )

    telegram_message_id = _extract_telegram_message_id(sent)

    print(
        f"AI REPLY BUTTON RESEND RESULT new_action_id={new_action_id} telegram_message_id={telegram_message_id}",
        flush=True,
    )

    if new_action_id and telegram_message_id:
        update_action_telegram_message_id(new_action_id, telegram_message_id)


def run_reply_ai_message_in_thread(user_id, bot_id, chat_id, action_id):
    threading.Thread(
        target=reply_ai_message,
        args=(user_id, bot_id, chat_id, action_id),
        daemon=True,
    ).start()


def run_regenerate_in_thread(user_id, bot_id, chat_id, action_id):
    threading.Thread(
        target=regenerate_ai_message,
        args=(user_id, bot_id, chat_id, action_id),
        daemon=True,
    ).start()


def run_continue_in_thread(user_id, bot_id, chat_id, action_id):
    threading.Thread(
        target=continue_ai_message,
        args=(user_id, bot_id, chat_id, action_id),
        daemon=True,
    ).start()
