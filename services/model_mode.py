from typing import Any, Dict

from services.database import get_conn
from services.telegram_service import send_message


MODE_MAIN = "main"
MODE_SECONDARY = "secondary"
VALID_MODES = {MODE_MAIN, MODE_SECONDARY}


def _text(value: Any) -> str:
    return str(value or "").strip()


def get_api_model_mode(user_id: Any, bot_id: Any, chat_id: Any) -> str:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT mode
            FROM api_model_modes
            WHERE user_id=%s AND bot_id=%s AND chat_id=%s
            """,
            (_text(user_id), _text(bot_id), _text(chat_id)),
        )
        row = cursor.fetchone()
        mode = _text(row[0]) if row else MODE_MAIN
        return mode if mode in VALID_MODES else MODE_MAIN
    finally:
        conn.close()


def set_api_model_mode(user_id: Any, bot_id: Any, chat_id: Any, mode: str) -> str:
    mode = _text(mode).lower()
    if mode not in VALID_MODES:
        raise ValueError("不支援的模型模式")

    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO api_model_modes (user_id, bot_id, chat_id, mode, updated_at)
            VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, bot_id, chat_id)
            DO UPDATE SET mode=EXCLUDED.mode, updated_at=CURRENT_TIMESTAMP
            """,
            (_text(user_id), _text(bot_id), _text(chat_id), mode),
        )
        conn.commit()
    finally:
        conn.close()

    print(
        f"MODEL MODE SET user_id={_text(user_id)} bot_id={_text(bot_id)} "
        f"chat_id={_text(chat_id)} mode={mode}",
        flush=True,
    )
    return mode


def toggle_api_model_mode(user_id: Any, bot_id: Any, chat_id: Any) -> str:
    current = get_api_model_mode(user_id, bot_id, chat_id)
    target = MODE_SECONDARY if current == MODE_MAIN else MODE_MAIN
    return set_api_model_mode(user_id, bot_id, chat_id, target)


def _mode_text(mode: str) -> str:
    if mode == MODE_SECONDARY:
        return "副模型（AI Horde）"
    return "主模型（Gemini）"


def handle_modes_api_command(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    command_text: str,
) -> Dict[str, Any]:
    parts = _text(command_text).split(maxsplit=1)
    arg = _text(parts[1]).lower() if len(parts) > 1 else ""

    print(
        f"MODEL MODE COMMAND user_id={_text(user_id)} bot_id={_text(bot_id)} "
        f"chat_id={_text(chat_id)} arg={arg or 'toggle'}",
        flush=True,
    )

    if arg in {"status", "狀態"}:
        mode = get_api_model_mode(user_id, bot_id, chat_id)
    elif arg in {"main", "gemini", "主", "主模型"}:
        mode = set_api_model_mode(user_id, bot_id, chat_id, MODE_MAIN)
    elif arg in {"secondary", "horde", "副", "副模型"}:
        mode = set_api_model_mode(user_id, bot_id, chat_id, MODE_SECONDARY)
    elif not arg:
        mode = toggle_api_model_mode(user_id, bot_id, chat_id)
    else:
        send_message(
            bot_id,
            chat_id,
            "用法：\n/modes_api\n/modes_api main\n/modes_api secondary\n/modes_api status",
        )
        return {"ok": False, "reason": "invalid_arg"}

    send_message(
        bot_id,
        chat_id,
        f"目前模型模式：{_mode_text(mode)}\n"
        + (
            "後續一般回覆、重跑、接續與救援回覆都會走副模型；輸入 /modes_api main 可切回 Gemini。"
            if mode == MODE_SECONDARY
            else "後續一般回覆、重跑、接續與救援回覆都會走 Gemini；安全阻擋按鈕仍可啟動主副模型競速。"
        ),
    )
    return {"ok": True, "mode": mode}
