from services.database import get_conn
from services.telegram_service import send_message


# =========================
# 全體使用者一次性公告
# =========================
# NOTICE_ID 只要換一個新字串，就會再對所有 user + bot 發一次。
NOTICE_ID = "major_update_memory_actions_time_20260705"

NOTICE_TEXT = """【系統更新公告】 
更新重點： 
1. 記憶系統更新 
新增重點記憶，用來客製化記憶。按鈕放在 [記憶設定]中。 
2. 設定頁隱私保護 
所有輸入設定用網頁額外加密，只有當下操作時自動獲取隨機金鑰解密。
解密時，操作時效 15 分鐘，請在時效內按下儲存。 
3. AI 回覆操作新增功能 
✏️ 修改文字　🔁 重新回覆　▶️ 接著回覆 
4. 安全提示 
內容被AI阻擋時會顯示「內容被安全阻擋」。 
        成人內容金鑰問我要
系統自動整理長期記憶被阻擋時會顯示「摘要長期記憶時被阻擋」。
        金鑰BLOCK_NONE（不封鎖任何內容）寫在摘要時，因為沒人能聊到儲存長 
        期記憶，所以還在測試
要是被阻擋，目前解決辦法只能把記憶全刪重聊

5. 時間感知 
聊天模式AI會自動帶入當下時間，回覆會更自然，希望吧。"""


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
