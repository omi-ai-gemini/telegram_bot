from services.database import get_conn
from services.crypto_env import encrypt_text, decrypt_text, aad_for
from services.gemini_service import summarize_memory, MEMORY_SUMMARY_BLOCKED
from services.telegram_service import send_message
from services.runtime_cache import get_cache, set_cache, delete_cache


# =========================
# 長期摘要設定
# =========================
SHORT_TERM_KEEP_MESSAGES = 100
SUMMARY_CHUNK_SIZE_MESSAGES = 100
ACTIVE_SUMMARY_KEEP = 12
ARCHIVE_BATCH_SIZE = 6
ARCHIVE_KEEP = 5


def _notify_summary_blocked(bot_id, chat_id):
    """摘要任務被 Gemini 安全層擋下時，直接回聊天室提示。"""
    try:
        send_message(bot_id, chat_id, "摘要長期記憶時被阻擋")
    except Exception as exc:
        print("TELEGRAM notify summary blocked error:", exc)


def _is_summary_blocked(value):
    return value == MEMORY_SUMMARY_BLOCKED


def _text_id(value):
    return str(value)


def _get_scope(chat_id):
    chat_id = str(chat_id)
    return "group" if int(chat_id) < 0 else "private"


def _memory_context_cache_prefix(bot_id, chat_id, scope):
    return ("memory_context", _text_id(bot_id), _text_id(chat_id), _text_id(scope))


def clear_memory_context_cache(bot_id, chat_id, scope=None):
    scope = _text_id(scope or _get_scope(chat_id))
    delete_cache(_memory_context_cache_prefix(bot_id, chat_id, scope))


def _decrypt_safe(value, aad=""):
    try:
        return decrypt_text(value, aad=aad)
    except Exception as exc:
        print("DECRYPT ERROR summary memory skipped:", exc)
        return ""


def _fetch_unsummarized_rows(cursor, bot_id, chat_id, scope, limit):
    cursor.execute("""
        SELECT last_summarized_chat_id
        FROM memory_summary_state
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
    """, (bot_id, chat_id, scope))

    row = cursor.fetchone()
    last_id = int(row[0]) if row and row[0] is not None else 0

    cursor.execute("""
        SELECT id, role, text
        FROM chat_memory
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
          AND id > %s
        ORDER BY id ASC
        LIMIT %s
    """, (bot_id, chat_id, scope, last_id, limit))

    return cursor.fetchall()


def _rows_to_plain_text(bot_id, chat_id, scope, rows):
    lines = []

    for row_id, role, value in rows:
        role = role or "user"
        aad = aad_for("chat_memory", "text", bot_id, chat_id, scope, role)
        text = _decrypt_safe(value, aad=aad)

        if not text:
            continue

        lines.append(f"{row_id}. {role}: {text}")

    return "\n".join(lines)


def _save_memory_summary(cursor, bot_id, chat_id, scope, start_chat_id, end_chat_id, summary):
    aad = aad_for("memory_summaries", "summary", bot_id, chat_id, scope, start_chat_id, end_chat_id)
    encrypted_summary = encrypt_text(summary, aad=aad)

    cursor.execute("""
        INSERT INTO memory_summaries (
            bot_id,
            chat_id,
            scope,
            start_chat_id,
            end_chat_id,
            summary,
            summary_type,
            is_archived,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'segment', FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (bot_id, chat_id, scope, start_chat_id, end_chat_id)
        DO UPDATE SET
            summary = EXCLUDED.summary,
            updated_at = CURRENT_TIMESTAMP,
            is_archived = FALSE
        RETURNING id
    """, (
        bot_id,
        chat_id,
        scope,
        start_chat_id,
        end_chat_id,
        encrypted_summary
    ))

    row = cursor.fetchone()
    return int(row[0]) if row else None


def _update_summary_state(cursor, bot_id, chat_id, scope, end_chat_id):
    cursor.execute("""
        INSERT INTO memory_summary_state (
            bot_id,
            chat_id,
            scope,
            last_summarized_chat_id,
            updated_at
        )
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (bot_id, chat_id, scope)
        DO UPDATE SET
            last_summarized_chat_id = GREATEST(memory_summary_state.last_summarized_chat_id, EXCLUDED.last_summarized_chat_id),
            updated_at = CURRENT_TIMESTAMP
    """, (bot_id, chat_id, scope, end_chat_id))


def _get_memory_state(cursor, bot_id, chat_id, scope):
    cursor.execute("""
        SELECT state
        FROM memory_state
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
    """, (bot_id, chat_id, scope))

    row = cursor.fetchone()
    if not row:
        return ""

    aad = aad_for("memory_state", "state", bot_id, chat_id, scope)
    return _decrypt_safe(row[0], aad=aad)


def _save_memory_state(cursor, bot_id, chat_id, scope, state_text):
    aad = aad_for("memory_state", "state", bot_id, chat_id, scope)
    encrypted_state = encrypt_text(state_text, aad=aad)

    cursor.execute("""
        INSERT INTO memory_state (
            bot_id,
            chat_id,
            scope,
            state,
            updated_at
        )
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (bot_id, chat_id, scope)
        DO UPDATE SET
            state = EXCLUDED.state,
            updated_at = CURRENT_TIMESTAMP
    """, (bot_id, chat_id, scope, encrypted_state))


def _refresh_memory_state(gemini_key, bot_id, chat_id, scope, new_summary):
    conn = get_conn()

    try:
        cursor = conn.cursor()
        current_state = _get_memory_state(cursor, bot_id, chat_id, scope)

        state_text = summarize_memory(
            gemini_key=gemini_key,
            source_text=(
                "既有目前狀態：\n"
                f"{current_state or '尚無'}\n\n"
                "新分段摘要：\n"
                f"{new_summary}"
            ),
            summary_type="state"
        )

        if _is_summary_blocked(state_text):
            _notify_summary_blocked(bot_id, chat_id)
            print("DEBUG memory state blocked by Gemini safety")
            return

        if state_text:
            _save_memory_state(cursor, bot_id, chat_id, scope, state_text)
            conn.commit()
            print("DEBUG memory state refreshed:", bot_id, chat_id, scope)

    except Exception as exc:
        conn.rollback()
        print("DB ERROR refresh_memory_state:", exc)

    finally:
        conn.close()


def _prune_short_memory(cursor, bot_id, chat_id, scope):
    cursor.execute("""
        SELECT last_summarized_chat_id
        FROM memory_summary_state
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
    """, (bot_id, chat_id, scope))

    row = cursor.fetchone()
    last_summarized_id = int(row[0]) if row and row[0] is not None else 0

    if last_summarized_id <= 0:
        return 0

    cursor.execute("""
        DELETE FROM chat_memory
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
          AND id <= %s
          AND id NOT IN (
              SELECT id
              FROM chat_memory
              WHERE bot_id = %s
                AND chat_id = %s
                AND scope = %s
              ORDER BY id DESC
              LIMIT %s
          )
    """, (
        bot_id,
        chat_id,
        scope,
        last_summarized_id,
        bot_id,
        chat_id,
        scope,
        SHORT_TERM_KEEP_MESSAGES
    ))

    return cursor.rowcount or 0


def summarize_pending_memory(gemini_key, bot_id, chat_id, user_id=None, max_chunks=2):
    """
    每累積 100 則尚未摘要的 chat_memory（約 50 輪對話），就產生一段 memory_summaries。
    預設一次最多補 2 段，避免單次請求太慢。
    """
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    completed = 0

    for _ in range(max_chunks):
        conn = get_conn()
        start_chat_id = None
        end_chat_id = None

        try:
            cursor = conn.cursor()
            rows = _fetch_unsummarized_rows(cursor, bot_id, chat_id, scope, SUMMARY_CHUNK_SIZE_MESSAGES)

            if len(rows) < SUMMARY_CHUNK_SIZE_MESSAGES:
                pruned = _prune_short_memory(cursor, bot_id, chat_id, scope)
                conn.commit()
                if pruned:
                    print("DEBUG short memory pruned:", pruned)
                return completed

            start_chat_id = int(rows[0][0])
            end_chat_id = int(rows[-1][0])
            raw_text = _rows_to_plain_text(bot_id, chat_id, scope, rows)

            if not raw_text.strip():
                _update_summary_state(cursor, bot_id, chat_id, scope, end_chat_id)
                conn.commit()
                continue

        except Exception as exc:
            conn.rollback()
            print("DB ERROR summarize_pending_memory read:", exc)
            return completed

        finally:
            conn.close()

        summary_text = summarize_memory(
            gemini_key=gemini_key,
            source_text=raw_text,
            summary_type="segment"
        )

        if _is_summary_blocked(summary_text):
            _notify_summary_blocked(bot_id, chat_id)
            print("DEBUG memory summary blocked by Gemini safety")
            return completed

        if not summary_text:
            print("DEBUG memory summary skipped: empty summary")
            return completed

        conn = get_conn()

        try:
            cursor = conn.cursor()
            _save_memory_summary(cursor, bot_id, chat_id, scope, start_chat_id, end_chat_id, summary_text)
            _update_summary_state(cursor, bot_id, chat_id, scope, end_chat_id)
            pruned = _prune_short_memory(cursor, bot_id, chat_id, scope)
            conn.commit()

            completed += 1
            print("DEBUG memory chunk summarized:", start_chat_id, end_chat_id, "pruned=", pruned)

        except Exception as exc:
            conn.rollback()
            print("DB ERROR summarize_pending_memory save:", exc)
            return completed

        finally:
            conn.close()

        _refresh_memory_state(gemini_key, bot_id, chat_id, scope, summary_text)

    return completed


def _fetch_active_summaries(cursor, bot_id, chat_id, scope, limit=None, oldest_first=True):
    order = "ASC" if oldest_first else "DESC"
    sql = f"""
        SELECT id, start_chat_id, end_chat_id, summary
        FROM memory_summaries
        WHERE bot_id = %s
          AND chat_id = %s
          AND scope = %s
          AND is_archived = FALSE
        ORDER BY start_chat_id {order}
    """

    params = [bot_id, chat_id, scope]

    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    result = []

    for summary_id, start_id, end_id, value in rows:
        aad = aad_for("memory_summaries", "summary", bot_id, chat_id, scope, start_id, end_id)
        text = _decrypt_safe(value, aad=aad)
        if text:
            result.append({
                "id": int(summary_id),
                "start_chat_id": int(start_id),
                "end_chat_id": int(end_id),
                "summary": text
            })

    return result


def cleanup_long_term_memory(gemini_key, bot_id, chat_id, user_id=None):
    """
    定期清理長期記憶：
    - active memory_summaries 超過 12 段時，最舊 6 段壓成 archive。
    - archives 超過 5 段時，再把更舊 archive 合併成一段。
    """
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _get_scope(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()
        active = _fetch_active_summaries(cursor, bot_id, chat_id, scope, oldest_first=True)
    except Exception as exc:
        print("DB ERROR cleanup_long_term_memory read:", exc)
        active = []
    finally:
        conn.close()

    if len(active) <= ACTIVE_SUMMARY_KEEP:
        return False

    batch = active[:ARCHIVE_BATCH_SIZE]

    source = "\n\n".join([
        f"摘要段落 {item['start_chat_id']}～{item['end_chat_id']}：\n{item['summary']}"
        for item in batch
    ])

    archive_text = summarize_memory(
        gemini_key=gemini_key,
        source_text=source,
        summary_type="archive"
    )

    if _is_summary_blocked(archive_text):
        _notify_summary_blocked(bot_id, chat_id)
        print("DEBUG archive summary blocked by Gemini safety")
        return False

    if not archive_text:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        start_summary_id = batch[0]["id"]
        end_summary_id = batch[-1]["id"]
        aad = aad_for("memory_archives", "archive_text", bot_id, chat_id, scope, start_summary_id, end_summary_id)
        encrypted_archive = encrypt_text(archive_text, aad=aad)

        cursor.execute("""
            INSERT INTO memory_archives (
                bot_id,
                chat_id,
                scope,
                start_summary_id,
                end_summary_id,
                archive_text,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (bot_id, chat_id, scope, start_summary_id, end_summary_id, encrypted_archive))

        cursor.execute("""
            UPDATE memory_summaries
            SET is_archived = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND id = ANY(%s)
        """, (bot_id, chat_id, scope, [item["id"] for item in batch]))

        conn.commit()
        print("DEBUG long memory archived:", start_summary_id, end_summary_id)

    except Exception as exc:
        conn.rollback()
        print("DB ERROR cleanup_long_term_memory save:", exc)
        return False

    finally:
        conn.close()

    _merge_old_archives_if_needed(gemini_key, bot_id, chat_id, scope)
    return True


def _merge_old_archives_if_needed(gemini_key, bot_id, chat_id, scope):
    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, start_summary_id, end_summary_id, archive_text
            FROM memory_archives
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id ASC
        """, (bot_id, chat_id, scope))

        rows = cursor.fetchall()

    except Exception as exc:
        print("DB ERROR merge archives read:", exc)
        return False

    finally:
        conn.close()

    if len(rows) <= ARCHIVE_KEEP:
        return False

    merge_rows = rows[: len(rows) - ARCHIVE_KEEP + 1]
    keep_ids = [int(row[0]) for row in rows[len(rows) - ARCHIVE_KEEP + 1:]]
    plain_parts = []

    for archive_id, start_id, end_id, value in merge_rows:
        aad = aad_for("memory_archives", "archive_text", bot_id, chat_id, scope, start_id, end_id)
        text = _decrypt_safe(value, aad=aad)
        if text:
            plain_parts.append(f"封存段 {start_id}～{end_id}:\n{text}")

    merged_text = summarize_memory(
        gemini_key=gemini_key,
        source_text="\n\n".join(plain_parts),
        summary_type="archive"
    )

    if _is_summary_blocked(merged_text):
        _notify_summary_blocked(bot_id, chat_id)
        print("DEBUG archive merge blocked by Gemini safety")
        return False

    if not merged_text:
        return False

    conn = get_conn()

    try:
        cursor = conn.cursor()
        start_summary_id = int(merge_rows[0][1])
        end_summary_id = int(merge_rows[-1][2])
        aad = aad_for("memory_archives", "archive_text", bot_id, chat_id, scope, start_summary_id, end_summary_id)
        encrypted = encrypt_text(merged_text, aad=aad)

        cursor.execute("""
            DELETE FROM memory_archives
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
              AND id <> ALL(%s)
        """, (bot_id, chat_id, scope, keep_ids))

        cursor.execute("""
            INSERT INTO memory_archives (
                bot_id,
                chat_id,
                scope,
                start_summary_id,
                end_summary_id,
                archive_text,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (bot_id, chat_id, scope, start_summary_id, end_summary_id, encrypted))

        conn.commit()
        print("DEBUG old archives merged")
        return True

    except Exception as exc:
        conn.rollback()
        print("DB ERROR merge archives save:", exc)
        return False

    finally:
        conn.close()


def maintain_memory_after_reply(gemini_key, bot_id, chat_id, user_id=None):
    """
    AI 成功回覆並寫入 assistant 短期記憶後呼叫。
    """
    chunks = summarize_pending_memory(gemini_key, bot_id, chat_id, user_id=user_id)

    if chunks:
        cleanup_long_term_memory(gemini_key, bot_id, chat_id, user_id=user_id)
        clear_memory_context_cache(bot_id, chat_id)

    return chunks


def list_memory_summaries(bot_id, chat_id, scope=None, limit=6):
    """列出最近 N 筆未封存摘要記憶，給 /memory 查看與單筆刪除使用。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))

    try:
        limit = int(limit or 6)
    except Exception:
        limit = 6

    limit = max(1, min(limit, 12))

    conn = get_conn()

    try:
        cursor = conn.cursor()
        items = _fetch_active_summaries(
            cursor,
            bot_id,
            chat_id,
            scope,
            limit=limit,
            oldest_first=False
        )
        return items

    except Exception as exc:
        print("DB ERROR list_memory_summaries:", exc)
        return []

    finally:
        conn.close()


def delete_memory_summary(summary_id, bot_id, chat_id, scope=None):
    """刪除單筆摘要記憶。"""
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))

    try:
        summary_id = int(summary_id)
    except Exception:
        return False, "summary_id 格式錯誤"

    conn = get_conn()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM memory_summaries
            WHERE id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND scope = %s
        """, (summary_id, bot_id, chat_id, scope))

        if cursor.rowcount == 0:
            conn.rollback()
            return False, "找不到這筆摘要記憶"

        conn.commit()
        clear_memory_context_cache(bot_id, chat_id, scope)
        return True, "已刪除摘要記憶"

    except Exception as exc:
        conn.rollback()
        print("DB ERROR delete_memory_summary:", exc)
        return False, "刪除摘要記憶失敗"

    finally:
        conn.close()


def get_memory_context(bot_id, chat_id, scope=None, user_id=None, summary_limit=4, archive_limit=2):
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)
    scope = _text_id(scope or _get_scope(chat_id))
    cache_key = _memory_context_cache_prefix(bot_id, chat_id, scope) + (
        int(summary_limit or 4),
        int(archive_limit or 2),
    )

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    conn = get_conn()

    try:
        cursor = conn.cursor()
        state_text = _get_memory_state(cursor, bot_id, chat_id, scope)

        active = _fetch_active_summaries(
            cursor,
            bot_id,
            chat_id,
            scope,
            limit=summary_limit,
            oldest_first=False
        )
        active = list(reversed(active))

        cursor.execute("""
            SELECT start_summary_id, end_summary_id, archive_text
            FROM memory_archives
            WHERE bot_id = %s
              AND chat_id = %s
              AND scope = %s
            ORDER BY id DESC
            LIMIT %s
        """, (bot_id, chat_id, scope, archive_limit))

        archives = []

        for start_id, end_id, value in cursor.fetchall():
            aad = aad_for("memory_archives", "archive_text", bot_id, chat_id, scope, start_id, end_id)
            text = _decrypt_safe(value, aad=aad)
            if text:
                archives.append({
                    "start_summary_id": int(start_id),
                    "end_summary_id": int(end_id),
                    "archive": text
                })

        context = {
            "state": state_text,
            "summaries": active,
            "archives": list(reversed(archives)),
        }

        return set_cache(cache_key, context, ttl=60)

    except Exception as exc:
        print("DB ERROR get_memory_context:", exc)
        return {
            "state": "",
            "summaries": [],
            "archives": [],
        }

    finally:
        conn.close()
