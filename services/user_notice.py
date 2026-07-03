from services.database import get_conn
from services.telegram_service import send_message


# =========================
# 全體使用者一次性公告
# =========================
# NOTICE_ID 只要換一個新字串，就會再對所有 user + bot 發一次。
NOTICE_ID = "privacy_memory_encryption_20260704"

NOTICE_TEXT = """【系統公告】
為了保護資料庫隱私，所有記憶資料在後台已經加密保存。

資料只會在提供給 Gemini 產生回覆時暫時解密；後台資料庫不會直接保存可讀明文記憶。

本次更新已刪除既有歷史紀錄，因此 AI 可能會有斷片狀況，需要重新投餵記憶。"""


def _text_id(value):
    return str(value)


def send_once_user_notice(user_id, bot_id, chat_id):
    """
    每個 user_id + bot_id + notice_id 只發一次公告。

    注意：
    - 不用預先知道所有使用者。
    - 使用者下一次傳訊息時自動收到。
    - 群組內會送到當下觸發訊息的 chat_id。
    """
    user_id = _text_id(user_id)
    bot_id = _text_id(bot_id)
    chat_id = _text_id(chat_id)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO user_notice_log (
                user_id,
                bot_id,
                notice_id,
                delivered_chat_id,
                delivered_at
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, bot_id, notice_id)
            DO NOTHING
            RETURNING user_id
            """,
            (
                user_id,
                bot_id,
                NOTICE_ID,
                chat_id,
            )
        )

        inserted = cursor.fetchone()
        conn.commit()

    except Exception as exc:
        conn.rollback()
        print("DB ERROR send_once_user_notice:", exc)
        return False

    finally:
        conn.close()

    if not inserted:
        return False

    sent = send_message(bot_id, chat_id, NOTICE_TEXT)

    if sent:
        print("DEBUG user notice sent:", NOTICE_ID, "user_id=", user_id, "bot_id=", bot_id)
    else:
        print("DEBUG user notice send failed:", NOTICE_ID, "user_id=", user_id, "bot_id=", bot_id)

    return sent
