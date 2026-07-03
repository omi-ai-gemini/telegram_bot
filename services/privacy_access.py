import threading
import time
from typing import Any, Optional, Tuple

from services.database import get_conn
from services.encrypted_store import create_user_unlock_code
from services.telegram_service import send_message
from services.privacy_session import set_unlock_code


# =========================
# 隱私管理權限 / 資料庫密碼自動補發
# =========================
# 設計原則：
# 1. 不存明文密碼
# 2. 每個 user_id + bot_id 只發一次
# 3. 已發放狀態放 DB：privacy_access.unlock_code_issued
# 4. 已發放結果放記憶體快取，避免每次 Gemini 回覆前都查 DB
# 5. 群組內不公開丟密碼，會優先私訊使用者

_ISSUED_CACHE = set()
_PENDING_PRIVATE_CACHE = {}
_CACHE_LOCK = threading.Lock()
PENDING_PRIVATE_TTL_SECONDS = 600


PRIVACY_ITEMS_TEXT = "記憶資料、劇本資料、風格資料、人物設定資料、後續納入隱私保護的資料"


def _text_id(value: Any) -> str:
    return str(value)


def _is_group_chat(chat_id: Any) -> bool:
    try:
        return int(chat_id) < 0
    except Exception:
        return str(chat_id).startswith("-")


def _cache_key(user_id: Any, bot_id: Any) -> Tuple[str, str]:
    return (_text_id(user_id), _text_id(bot_id))


def _is_pending_private_notice_cached(key: Tuple[str, str]) -> bool:
    now = time.time()

    with _CACHE_LOCK:
        last_time = _PENDING_PRIVATE_CACHE.get(key)

        if not last_time:
            return False

        if now - last_time > PENDING_PRIVATE_TTL_SECONDS:
            _PENDING_PRIVATE_CACHE.pop(key, None)
            return False

        return True


def _mark_pending_private_notice(key: Tuple[str, str]) -> None:
    with _CACHE_LOCK:
        _PENDING_PRIVATE_CACHE[key] = time.time()


def _mark_issued_cache(key: Tuple[str, str]) -> None:
    with _CACHE_LOCK:
        _ISSUED_CACHE.add(key)
        _PENDING_PRIVATE_CACHE.pop(key, None)


def _is_issued_cached(key: Tuple[str, str]) -> bool:
    with _CACHE_LOCK:
        return key in _ISSUED_CACHE


def build_privacy_password_message(unlock_code: str) -> str:
    return (
        "資料庫新增隱私管理權限\n"
        "個別資料庫密碼：\n"
        f"{unlock_code}\n\n"
        "妥善保存密碼，遺失就無法後台修改。\n"
        f"隱私保護項目：{PRIVACY_ITEMS_TEXT}\n\n"
        "注意：系統不會保存這組密碼明文，之後也不會再次顯示。"
    )


def _send_unlock_code_safely(user_id: str, bot_id: str, chat_id: str, unlock_code: str) -> bool:
    """
    私聊：直接傳目前聊天室。
    群組：優先私訊 user_id，避免把個人密碼丟進群組。
    """

    target_chat_id = user_id if _is_group_chat(chat_id) else chat_id

    ok = send_message(
        bot_id,
        target_chat_id,
        build_privacy_password_message(unlock_code)
    )

    return bool(ok)


def ensure_privacy_password_issued(user_id: Any, bot_id: Any, chat_id: Any) -> bool:
    """
    確保目前 user_id + bot_id 已經拿過資料庫密碼。

    回傳：
    - True：本次有成功發放新密碼
    - False：已發放過 / 發放失敗 / 略過

    效能：
    - 已發放者會進 _ISSUED_CACHE
    - 同一個 Render process 後續不查 DB
    - DB 仍是最終狀態來源，重啟後第一次才會查
    """

    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    key = _cache_key(user_id, bot_id)

    if _is_issued_cached(key):
        return False

    # 群組中如果剛提醒過「請先私訊 bot」，10 分鐘內不重複打擾，也避免每句都查 DB。
    if _is_group_chat(chat_id) and _is_pending_private_notice_cached(key):
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT unlock_code_issued, delivery_status
            FROM privacy_access
            WHERE user_id = %s
              AND bot_id = %s
            """,
            (user_id, bot_id),
        )

        row = cursor.fetchone()

        if row and row[0] is True:
            _mark_issued_cache(key)
            return False

        # 如果是在群組，而且之前已經標記需要私訊，就不要每次都重送。
        if _is_group_chat(chat_id) and row and row[1] == "need_private_chat":
            _mark_pending_private_notice(key)
            return False

        unlock_code = create_user_unlock_code()

        sent = _send_unlock_code_safely(
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            unlock_code=unlock_code,
        )

        if not sent:
            # 群組不能把密碼公開丟出來，所以只提示使用者先私訊 bot。
            # 不標記 issued，之後使用者進私聊時還是會拿到真正密碼。
            delivery_status = "need_private_chat" if _is_group_chat(chat_id) else "send_failed"

            cursor.execute(
                """
                INSERT INTO privacy_access (
                    user_id,
                    bot_id,
                    unlock_code_issued,
                    delivery_status,
                    updated_at
                )
                VALUES (%s, %s, FALSE, %s, CURRENT_TIMESTAMP)

                ON CONFLICT (user_id, bot_id)

                DO UPDATE SET
                    unlock_code_issued = FALSE,
                    delivery_status = EXCLUDED.delivery_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, bot_id, delivery_status),
            )

            conn.commit()

            if _is_group_chat(chat_id):
                send_message(
                    bot_id,
                    chat_id,
                    "我需要私訊傳送你的隱私管理密碼，但目前無法私訊你。請先到我的私人聊天室傳一則訊息，再回來繼續使用。"
                )
                _mark_pending_private_notice(key)

            return False

        cursor.execute(
            """
            INSERT INTO privacy_access (
                user_id,
                bot_id,
                unlock_code_issued,
                delivery_status,
                issued_chat_id,
                issued_at,
                updated_at
            )
            VALUES (%s, %s, TRUE, 'issued', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)

            ON CONFLICT (user_id, bot_id)

            DO UPDATE SET
                unlock_code_issued = TRUE,
                delivery_status = 'issued',
                issued_chat_id = EXCLUDED.issued_chat_id,
                issued_at = COALESCE(privacy_access.issued_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, bot_id, chat_id),
        )

        conn.commit()
        _mark_issued_cache(key)
        # 同步：密碼發出去的同一刻，也放進本次 Render 記憶體，後續新寫入才能立刻加密。
        set_unlock_code(user_id, bot_id, unlock_code)
        return True

    except Exception as exc:
        conn.rollback()
        print("DB ERROR ensure_privacy_password_issued:", exc)
        return False

    finally:
        conn.close()


def has_privacy_password_issued(user_id: Any, bot_id: Any) -> bool:
    """需要後台判斷時可用；不會產生密碼。"""

    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    key = _cache_key(user_id, bot_id)

    if _is_issued_cached(key):
        return True

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT unlock_code_issued
            FROM privacy_access
            WHERE user_id = %s
              AND bot_id = %s
            """,
            (user_id, bot_id),
        )

        row: Optional[tuple] = cursor.fetchone()
        issued = bool(row and row[0] is True)

        if issued:
            _mark_issued_cache(key)

        return issued

    finally:
        conn.close()
