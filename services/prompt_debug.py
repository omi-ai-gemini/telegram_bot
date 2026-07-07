import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json
from urllib.parse import urlencode

from services.database import get_conn


# =========================
# Prompt Debug 開發者工具
# =========================
# 目的：
# - 每次主遊戲呼叫 Gemini 前，保存實際送入 contents=prompt 的完整文字。
# - 不把 prompt 丟進 Telegram 聊天室，避免訊息過長造成 App 閃退。
# - 透過簽章網址進入網頁查看 / 比對，降低外流風險。

PROMPT_DEBUG_TOKEN_TTL_SECONDS = 60 * 30
PROMPT_DEBUG_KEEP_PER_CHAT = 50


def _text_id(value: Any) -> str:
    return str(value or "").strip()


def _token_secret() -> bytes:
    secret = (
        os.getenv("SETTING_LINK_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("FLASK_SECRET_KEY")
        or ""
    )

    if not secret:
        # 開發環境保底，正式環境請務必設定 SECRET_KEY / SETTING_LINK_SECRET。
        secret = "telemini-prompt-debug-dev-secret"

    return secret.encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_token_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_prompt_debug_token(user_id: Any, bot_id: Any, chat_id: Any, ttl_seconds: int = PROMPT_DEBUG_TOKEN_TTL_SECONDS) -> str:
    """建立短效簽章 token，避免 prompt debug 頁裸奔。"""
    exp = int(time.time()) + int(ttl_seconds or PROMPT_DEBUG_TOKEN_TTL_SECONDS)
    payload = "|".join([
        _text_id(user_id),
        _text_id(bot_id),
        _text_id(chat_id),
        str(exp),
    ])
    return f"{payload}|{_sign(payload)}"


def verify_prompt_debug_token(token: str, user_id: Any = None, bot_id: Any = None, chat_id: Any = None) -> Dict[str, Any]:
    """驗證 prompt debug token，回傳 token 內的 user/bot/chat。"""
    token = _text_id(token)

    try:
        parts = token.split("|")
        if len(parts) != 5:
            return {"ok": False, "reason": "bad_format"}

        token_user_id, token_bot_id, token_chat_id, exp_text, sig = parts
        payload = "|".join(parts[:4])

        if not hmac.compare_digest(sig, _sign(payload)):
            return {"ok": False, "reason": "bad_signature"}

        exp = int(exp_text)
        if exp < int(time.time()):
            return {"ok": False, "reason": "expired"}

        if user_id is not None and _text_id(user_id) != token_user_id:
            return {"ok": False, "reason": "user_mismatch"}
        if bot_id is not None and _text_id(bot_id) != token_bot_id:
            return {"ok": False, "reason": "bot_mismatch"}
        if chat_id is not None and _text_id(chat_id) != token_chat_id:
            return {"ok": False, "reason": "chat_mismatch"}

        return {
            "ok": True,
            "user_id": token_user_id,
            "bot_id": token_bot_id,
            "chat_id": token_chat_id,
            "expires_at": exp,
        }

    except Exception as exc:
        print("PROMPT DEBUG TOKEN VERIFY ERROR:", exc, flush=True)
        return {"ok": False, "reason": "exception"}


def _base_url() -> str:
    return os.getenv("BASE_URL", "").rstrip("/")


def build_prompt_debug_url(user_id: Any, bot_id: Any, chat_id: Any) -> Optional[str]:
    base_url = _base_url()
    if not base_url:
        return None

    token = create_prompt_debug_token(user_id, bot_id, chat_id)
    return f"{base_url}/prompt_debug?{urlencode({'token': token})}"


def build_prompt_debug_compare_url(user_id: Any, bot_id: Any, chat_id: Any, left_id: Any = None, right_id: Any = None) -> Optional[str]:
    base_url = _base_url()
    if not base_url:
        return None

    token = create_prompt_debug_token(user_id, bot_id, chat_id)
    query = {"token": token}
    if left_id:
        query["left_id"] = str(left_id)
    if right_id:
        query["right_id"] = str(right_id)

    return f"{base_url}/prompt_debug/compare?{urlencode(query)}"


def save_prompt_debug_log(
    prompt_text: Any,
    user_id: Any = None,
    bot_id: Any = None,
    chat_id: Any = None,
    source: str = "unknown",
    generation_type: str = "unknown",
    action_id: Any = None,
    source_user_chat_id: Any = None,
    model: str = "",
    prompt_meta: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """保存 Gemini 呼叫前的完整 prompt，回傳 debug log id。"""
    prompt_text = str(prompt_text or "")

    if not bot_id or not chat_id:
        return None

    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prompt_debug_logs (
                user_id,
                bot_id,
                chat_id,
                source,
                generation_type,
                action_id,
                source_user_chat_id,
                model,
                prompt_text,
                prompt_chars,
                prompt_hash,
                status,
                prompt_meta,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'built', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                _text_id(user_id),
                _text_id(bot_id),
                _text_id(chat_id),
                _text_id(source) or "unknown",
                _text_id(generation_type) or "unknown",
                int(action_id) if str(action_id or "").isdigit() else None,
                int(source_user_chat_id) if str(source_user_chat_id or "").isdigit() else None,
                _text_id(model),
                prompt_text,
                len(prompt_text),
                prompt_hash,
                Json(prompt_meta or {}),
            ),
        )
        row = cursor.fetchone()
        log_id = int(row[0]) if row else None

        # 每個 bot + chat 保留最新 N 筆，避免 debug 表無限成長。
        cursor.execute(
            """
            DELETE FROM prompt_debug_logs
            WHERE id IN (
                SELECT id FROM (
                    SELECT id
                    FROM prompt_debug_logs
                    WHERE bot_id = %s
                      AND chat_id = %s
                    ORDER BY id DESC
                    OFFSET %s
                ) old_rows
            )
            """,
            (_text_id(bot_id), _text_id(chat_id), PROMPT_DEBUG_KEEP_PER_CHAT),
        )

        conn.commit()
        return log_id

    except Exception as exc:
        conn.rollback()
        print("PROMPT DEBUG SAVE ERROR:", exc, flush=True)
        return None

    finally:
        conn.close()


def update_prompt_debug_log(log_id: Any, status: str = "", finish_reason: str = "", block_reason: str = "", response_chars: Any = None) -> bool:
    """Gemini 回來後補上結果狀態。"""
    if not log_id:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE prompt_debug_logs
            SET status = COALESCE(NULLIF(%s, ''), status),
                finish_reason = NULLIF(%s, ''),
                block_reason = NULLIF(%s, ''),
                response_chars = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                _text_id(status),
                _text_id(finish_reason),
                _text_id(block_reason),
                int(response_chars) if str(response_chars or "").isdigit() else None,
                int(log_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0

    except Exception as exc:
        conn.rollback()
        print("PROMPT DEBUG UPDATE ERROR:", exc, flush=True)
        return False

    finally:
        conn.close()


def list_prompt_debug_logs(bot_id: Any, chat_id: Any, user_id: Any = None, limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_conn()

    try:
        cursor = conn.cursor()
        params = [_text_id(bot_id), _text_id(chat_id)]
        user_filter = ""

        if user_id is not None:
            user_filter = "AND user_id = %s"
            params.append(_text_id(user_id))

        params.append(int(limit or 30))
        cursor.execute(
            f"""
            SELECT id, user_id, bot_id, chat_id, source, generation_type, action_id,
                   source_user_chat_id, model, prompt_chars, prompt_hash, status,
                   finish_reason, block_reason, response_chars, created_at, updated_at
            FROM prompt_debug_logs
            WHERE bot_id = %s
              AND chat_id = %s
              {user_filter}
            ORDER BY id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()
        return [_row_to_summary(row) for row in rows]

    except Exception as exc:
        print("PROMPT DEBUG LIST ERROR:", exc, flush=True)
        return []

    finally:
        conn.close()


def get_prompt_debug_log(log_id: Any, bot_id: Any, chat_id: Any, user_id: Any = None) -> Optional[Dict[str, Any]]:
    if not str(log_id or "").isdigit():
        return None

    conn = get_conn()

    try:
        cursor = conn.cursor()
        params = [int(log_id), _text_id(bot_id), _text_id(chat_id)]
        user_filter = ""

        if user_id is not None:
            user_filter = "AND user_id = %s"
            params.append(_text_id(user_id))

        cursor.execute(
            f"""
            SELECT id, user_id, bot_id, chat_id, source, generation_type, action_id,
                   source_user_chat_id, model, prompt_text, prompt_chars, prompt_hash,
                   status, finish_reason, block_reason, response_chars, prompt_meta,
                   created_at, updated_at
            FROM prompt_debug_logs
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              {user_filter}
            LIMIT 1
            """,
            params,
        )
        row = cursor.fetchone()
        return _row_to_detail(row) if row else None

    except Exception as exc:
        print("PROMPT DEBUG GET ERROR:", exc, flush=True)
        return None

    finally:
        conn.close()


def _format_dt(value: Any) -> str:
    if not value:
        return ""

    try:
        if hasattr(value, "isoformat"):
            return value.isoformat(sep=" ", timespec="seconds")
        return str(value)
    except Exception:
        return str(value)


def _row_to_summary(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "user_id": row[1],
        "bot_id": row[2],
        "chat_id": row[3],
        "source": row[4],
        "generation_type": row[5],
        "action_id": row[6],
        "source_user_chat_id": row[7],
        "model": row[8],
        "prompt_chars": row[9],
        "prompt_hash": row[10],
        "status": row[11],
        "finish_reason": row[12],
        "block_reason": row[13],
        "response_chars": row[14],
        "created_at": _format_dt(row[15]),
        "updated_at": _format_dt(row[16]),
    }


def _row_to_detail(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "user_id": row[1],
        "bot_id": row[2],
        "chat_id": row[3],
        "source": row[4],
        "generation_type": row[5],
        "action_id": row[6],
        "source_user_chat_id": row[7],
        "model": row[8],
        "prompt_text": row[9] or "",
        "prompt_chars": row[10],
        "prompt_hash": row[11],
        "status": row[12],
        "finish_reason": row[13],
        "block_reason": row[14],
        "response_chars": row[15],
        "prompt_meta": row[16] or {},
        "created_at": _format_dt(row[17]),
        "updated_at": _format_dt(row[18]),
    }


def send_prompt_debug_link(bot_id: Any, chat_id: Any, user_id: Any, compare: bool = False) -> bool:
    """Telegram 只送網頁入口，不把 prompt 灌進聊天室。"""
    from services.telegram_service import send_message

    url = build_prompt_debug_compare_url(user_id, bot_id, chat_id) if compare else build_prompt_debug_url(user_id, bot_id, chat_id)

    if not url:
        send_message(bot_id, chat_id, "Prompt Debug 需要先設定 BASE_URL，才能產生網頁連結。")
        return False

    title = "Prompt Debug 比對頁" if compare else "Prompt Debug 網頁"
    send_message(bot_id, chat_id, f"{title}：\n{url}")
    return True
