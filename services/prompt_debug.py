from services.database import get_conn
from services.telegram_service import send_message


# =========================
# Gemini Prompt Debug
# =========================
# 用途：
# - 開發者排查 Gemini prompt_block_reason / PROHIBITED_CONTENT。
# - 在每次主遊戲呼叫 Gemini 前，把「最後實際送入 contents 的完整 prompt」存進 DB。
# - 不寫 Render log，避免 prompt 明文在 log 外流。
#
# 注意：
# - 這是開發者除錯功能，prompt 內可能包含短期記憶、長期摘要、重點記憶、人物設定與自訂風格。
# - 只建議在開發期使用。
# - 每個 bot + chat 最多保留 PROMPT_DEBUG_KEEP_PER_CHAT 筆，避免資料庫無限制膨脹。

PROMPT_DEBUG_KEEP_PER_CHAT = 30
TELEGRAM_SAFE_CHUNK = 3400


def _text_id(value):
    return str(value or '').strip()


def _bool_text(value):
    return '1' if value else '0'


def save_prompt_debug_log(
    bot_id=None,
    chat_id=None,
    user_id=None,
    source='unknown',
    model='',
    mode='',
    prompt='',
    user_text='',
    include_thoughts=False,
    return_meta=False,
):
    """保存一筆 Gemini prompt debug log。

    這裡故意不加密，因為用途是讓開發者直接查看完整 prompt。
    但也因此不要把這個功能開給一般使用者。
    """
    prompt = str(prompt or '')

    if not prompt:
        return None

    bot_id = _text_id(bot_id or 'unknown')
    chat_id = _text_id(chat_id or 'unknown')
    user_id = _text_id(user_id or '')
    source = _text_id(source or 'unknown')
    model = _text_id(model or '')
    mode = _text_id(mode or '')
    user_text = str(user_text or '')

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prompt_debug_logs (
                bot_id,
                chat_id,
                user_id,
                source,
                model,
                mode,
                prompt_text,
                prompt_length,
                user_text_preview,
                include_thoughts,
                return_meta,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                bot_id,
                chat_id,
                user_id,
                source,
                model,
                mode,
                prompt,
                len(prompt),
                user_text[:500],
                bool(include_thoughts),
                bool(return_meta),
            ),
        )

        row = cursor.fetchone()
        log_id = row[0] if row else None

        # 只保留同 bot + chat 最新 N 筆。
        cursor.execute(
            """
            DELETE FROM prompt_debug_logs
            WHERE id IN (
                SELECT id
                FROM prompt_debug_logs
                WHERE bot_id = %s
                  AND chat_id = %s
                ORDER BY id DESC
                OFFSET %s
            )
            """,
            (bot_id, chat_id, PROMPT_DEBUG_KEEP_PER_CHAT),
        )

        conn.commit()

        print(
            f"PROMPT DEBUG SAVED id={log_id} source={source} bot_id={bot_id} "
            f"chat_id={chat_id} len={len(prompt)}",
            flush=True,
        )

        return log_id

    except Exception as exc:
        conn.rollback()
        print('PROMPT DEBUG SAVE ERROR:', exc, flush=True)
        return None

    finally:
        conn.close()


def list_prompt_debug_logs(bot_id, chat_id, limit=10):
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, source, model, mode, prompt_length, user_text_preview, created_at
            FROM prompt_debug_logs
            WHERE bot_id = %s
              AND chat_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (bot_id, chat_id, int(limit or 10)),
        )
        return cursor.fetchall()

    except Exception as exc:
        print('PROMPT DEBUG LIST ERROR:', exc, flush=True)
        return []

    finally:
        conn.close()


def get_prompt_debug_log(bot_id, chat_id, log_id=None):
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        if log_id:
            cursor.execute(
                """
                SELECT id, source, model, mode, prompt_length, user_text_preview,
                       include_thoughts, return_meta, created_at, prompt_text
                FROM prompt_debug_logs
                WHERE bot_id = %s
                  AND chat_id = %s
                  AND id = %s
                LIMIT 1
                """,
                (bot_id, chat_id, int(log_id)),
            )
        else:
            cursor.execute(
                """
                SELECT id, source, model, mode, prompt_length, user_text_preview,
                       include_thoughts, return_meta, created_at, prompt_text
                FROM prompt_debug_logs
                WHERE bot_id = %s
                  AND chat_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (bot_id, chat_id),
            )

        return cursor.fetchone()

    except Exception as exc:
        print('PROMPT DEBUG GET ERROR:', exc, flush=True)
        return None

    finally:
        conn.close()


def _send_long_text(bot_id, chat_id, text, header=''):
    text = str(text or '')
    header = str(header or '')

    if not text:
        send_message(bot_id, chat_id, header or '沒有內容')
        return

    chunks = [
        text[i:i + TELEGRAM_SAFE_CHUNK]
        for i in range(0, len(text), TELEGRAM_SAFE_CHUNK)
    ]

    total = len(chunks)

    if header:
        send_message(bot_id, chat_id, header)

    for index, chunk in enumerate(chunks, start=1):
        prefix = f'【PROMPT {index}/{total}】\n'
        send_message(bot_id, chat_id, prefix + chunk)


def send_prompt_debug_list(bot_id, chat_id, limit=10):
    rows = list_prompt_debug_logs(bot_id, chat_id, limit=limit)

    if not rows:
        send_message(bot_id, chat_id, '目前沒有 prompt debug 紀錄。先傳一句一般聊天，讓系統呼叫 Gemini 後再查。')
        return True

    lines = ['最近 prompt debug 紀錄：']

    for row in rows:
        log_id, source, model, mode, prompt_length, user_text_preview, created_at = row
        preview = ' '.join(str(user_text_preview or '').split())[:60]
        lines.append(
            f'#{log_id} | {source} | {mode or "-"} | len={prompt_length} | {created_at}\n'
            f'  input: {preview}'
        )

    lines.append('\n輸入 /prompt_debug <id> 可查看指定 prompt。')
    lines.append('輸入 /prompt_debug 可查看最新一筆完整 prompt。')

    send_message(bot_id, chat_id, '\n'.join(lines))
    return True


def send_prompt_debug_log(bot_id, chat_id, log_id=None):
    row = get_prompt_debug_log(bot_id, chat_id, log_id=log_id)

    if not row:
        send_message(bot_id, chat_id, '找不到 prompt debug 紀錄。')
        return True

    (
        row_id,
        source,
        model,
        mode,
        prompt_length,
        user_text_preview,
        include_thoughts,
        return_meta,
        created_at,
        prompt_text,
    ) = row

    header = (
        f'PROMPT DEBUG #{row_id}\n'
        f'source：{source}\n'
        f'model：{model or "-"}\n'
        f'mode：{mode or "-"}\n'
        f'len：{prompt_length}\n'
        f'include_thoughts：{_bool_text(include_thoughts)}\n'
        f'return_meta：{_bool_text(return_meta)}\n'
        f'created_at：{created_at}\n'
        f'user_text_preview：{str(user_text_preview or "")[:300]}'
    )

    _send_long_text(bot_id, chat_id, prompt_text, header=header)
    return True


def handle_prompt_debug_command(bot_id, chat_id, user_text):
    """處理開發者 prompt debug 指令。

    支援：
    - /prompt_debug：輸出最新一筆完整 prompt。
    - /prompt_debug_list：列出最近 10 筆。
    - /prompt_debug <id>：輸出指定 id 的完整 prompt。
    """
    text = str(user_text or '').strip()

    if text == '/prompt_debug_list':
        return send_prompt_debug_list(bot_id, chat_id, limit=10)

    if text == '/prompt_debug':
        return send_prompt_debug_log(bot_id, chat_id)

    if text.startswith('/prompt_debug '):
        value = text.split(None, 1)[1].strip()
        if not value.isdigit():
            send_message(bot_id, chat_id, '格式錯誤，請用 /prompt_debug <id>。')
            return True

        return send_prompt_debug_log(bot_id, chat_id, log_id=int(value))

    return False
