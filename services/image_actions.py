import os
from urllib.parse import urlencode
from typing import Any, Dict, Optional

from services.database import get_conn
from services.image_auth import create_image_token
from services.memory import get_chat_memory_item
from services.telegram_service import send_message


def _text(value: Any) -> str:
    return str(value or "").strip()


def _base_url() -> str:
    return str(os.getenv("BASE_URL") or "").rstrip("/")


def get_action_identity(action_id: Any) -> Optional[Dict[str, Any]]:
    try:
        action_id = int(action_id)
    except Exception:
        return None

    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bot_id, chat_id, user_id, assistant_chat_id,
                   source_user_chat_id, telegram_message_id
            FROM ai_message_actions
            WHERE id=%s
        """, (action_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "bot_id": row[1],
            "chat_id": row[2],
            "user_id": row[3],
            "assistant_chat_id": row[4],
            "source_user_chat_id": row[5],
            "telegram_message_id": row[6],
        }
    finally:
        conn.close()


def get_image_generation_url(action_id: Any) -> Optional[str]:
    base_url = _base_url()
    action = get_action_identity(action_id)
    if not base_url or not action or not action.get("user_id"):
        return None

    token = create_image_token(
        user_id=action["user_id"],
        bot_id=action["bot_id"],
        chat_id=action["chat_id"],
        page_type="generate",
        action_id=action["id"],
    )
    return f"{base_url}/image/generate?{urlencode({'token': token})}"


def get_image_library_url(user_id: Any, bot_id: Any, chat_id: Any) -> Optional[str]:
    base_url = _base_url()
    if not base_url or user_id is None:
        return None
    token = create_image_token(
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        page_type="library",
    )
    return f"{base_url}/setting/images?{urlencode({'token': token})}"


def load_action_context(action_id: Any, user_id: Any, bot_id: Any, chat_id: Any) -> Optional[Dict[str, Any]]:
    action = get_action_identity(action_id)
    if not action:
        return None

    if _text(action.get("user_id")) != _text(user_id):
        return None
    if _text(action.get("bot_id")) != _text(bot_id):
        return None
    if _text(action.get("chat_id")) != _text(chat_id):
        return None

    assistant = get_chat_memory_item(action.get("assistant_chat_id"), bot_id, chat_id)
    source_user = None
    if action.get("source_user_chat_id"):
        source_user = get_chat_memory_item(action.get("source_user_chat_id"), bot_id, chat_id)

    return {
        "action": action,
        "assistant_text": _text((assistant or {}).get("text")),
        "user_text": _text((source_user or {}).get("text")),
    }


def send_hidden_image_link(bot_id: Any, chat_id: Any, action_id: Any) -> bool:
    url = get_image_generation_url(action_id)
    if not url:
        send_message(bot_id, chat_id, "生圖設定連結尚未建立，請確認 BASE_URL / SETTING_LINK_SECRET")
        return False

    send_message(
        bot_id,
        chat_id,
        "開啟生圖設定",
        reply_markup={
            "inline_keyboard": [[
                {"text": "📸 開啟生圖設定", "url": url}
            ]]
        },
    )
    return True
