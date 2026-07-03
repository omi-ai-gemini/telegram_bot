import json
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from services.crypto_box import (
    build_aad,
    decrypt_payload,
    encrypt_payload,
    generate_unlock_code,
)
from services.database import get_conn


# =========================
# 通用加密資料存取層
# =========================
# 用法：
# - 明文欄位只保留 user_id / bot_id / chat_id / data_type / record_key
# - 真正內容全部包成 payload dict 後加密
# - 未來你改欄位，只改 payload 裡的 key，不用改加密流程


def create_user_unlock_code() -> str:
    """
    產生使用者解鎖碼。
    這個值只能顯示給使用者，不要存 DB 明文。
    """

    return generate_unlock_code()


def save_encrypted_payload(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    data_type: str,
    unlock_code: str,
    payload: Dict[str, Any],
    record_key: str = "default",
) -> None:
    """
    新增 / 更新一筆加密資料。

    data_type 範例：
    - chat_persona
    - character
    - reply_style
    - memory
    - api_key

    record_key 用途：
    - 同一個 data_type 如果只有一筆，用 default
    - 如果同類型有多筆，例如 memory，可用 memory_id 或 uuid
    """

    user_id = str(user_id)
    bot_id = str(bot_id)
    chat_id = str(chat_id)
    data_type = str(data_type)
    record_key = str(record_key or "default")

    aad = build_aad(user_id, bot_id, chat_id, data_type, record_key)
    encrypted_payload = encrypt_payload(unlock_code, payload, aad=aad)

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO encrypted_settings (
                user_id,
                bot_id,
                chat_id,
                data_type,
                record_key,
                encrypted_payload,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

            ON CONFLICT (user_id, bot_id, chat_id, data_type, record_key)

            DO UPDATE SET
                encrypted_payload = EXCLUDED.encrypted_payload,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                bot_id,
                chat_id,
                data_type,
                record_key,
                Json(encrypted_payload),
            ),
        )

        conn.commit()

    except Exception as exc:
        conn.rollback()
        print("DB ERROR save_encrypted_payload:", exc)
        raise

    finally:
        conn.close()


def get_encrypted_payload(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    data_type: str,
    unlock_code: str,
    record_key: str = "default",
) -> Optional[Dict[str, Any]]:
    """
    讀取並解密一筆資料。

    回傳：
    - 找不到資料：None
    - 成功：payload dict
    - 解鎖碼錯誤：丟 UnlockCodeError
    """

    user_id = str(user_id)
    bot_id = str(bot_id)
    chat_id = str(chat_id)
    data_type = str(data_type)
    record_key = str(record_key or "default")

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT encrypted_payload
            FROM encrypted_settings
            WHERE user_id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND data_type = %s
              AND record_key = %s
            """,
            (
                user_id,
                bot_id,
                chat_id,
                data_type,
                record_key,
            ),
        )

        row = cursor.fetchone()

        if not row:
            return None

        encrypted_payload = row[0]

        if isinstance(encrypted_payload, str):
            encrypted_payload = json.loads(encrypted_payload)

        aad = build_aad(user_id, bot_id, chat_id, data_type, record_key)

        return decrypt_payload(
            unlock_code=unlock_code,
            encrypted_data=encrypted_payload,
            aad=aad,
        )

    finally:
        conn.close()


def delete_encrypted_payload(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    data_type: str,
    record_key: str = "default",
) -> bool:
    """刪除一筆加密資料。"""

    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM encrypted_settings
            WHERE user_id = %s
              AND bot_id = %s
              AND chat_id = %s
              AND data_type = %s
              AND record_key = %s
            """,
            (
                str(user_id),
                str(bot_id),
                str(chat_id),
                str(data_type),
                str(record_key or "default"),
            ),
        )

        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    except Exception as exc:
        conn.rollback()
        print("DB ERROR delete_encrypted_payload:", exc)
        raise

    finally:
        conn.close()


def list_encrypted_metadata(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    data_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    只列出加密資料的索引，不解密內容。
    適合後台檢查有哪些資料存在。
    """

    conn = get_conn()

    try:
        cursor = conn.cursor()

        if data_type:
            cursor.execute(
                """
                SELECT data_type, record_key, created_at, updated_at
                FROM encrypted_settings
                WHERE user_id = %s
                  AND bot_id = %s
                  AND chat_id = %s
                  AND data_type = %s
                ORDER BY updated_at DESC
                """,
                (str(user_id), str(bot_id), str(chat_id), str(data_type)),
            )
        else:
            cursor.execute(
                """
                SELECT data_type, record_key, created_at, updated_at
                FROM encrypted_settings
                WHERE user_id = %s
                  AND bot_id = %s
                  AND chat_id = %s
                ORDER BY updated_at DESC
                """,
                (str(user_id), str(bot_id), str(chat_id)),
            )

        rows = cursor.fetchall()

        return [
            {
                "data_type": row[0],
                "record_key": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]

    finally:
        conn.close()
