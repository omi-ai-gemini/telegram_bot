from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_call_ai():
    path = ROOT / "services" / "call_ai.py"
    text = path.read_text(encoding="utf-8")

    if "def run_blocked_reply_retry(" in text:
        print("SKIP services/call_ai.py: run_blocked_reply_retry already exists")
        return

    marker = "# =========================\n# /reply 救援指令\n# =========================\n"
    if marker not in text:
        raise RuntimeError("services/call_ai.py: cannot find /reply marker")

    func = r'''
# =========================
# 安全阻擋提示按鈕：直接用最後一筆 user 記憶補生回覆
# =========================
def run_blocked_reply_retry(user_id: int, bot_id: str, chat_id: int):
    """
    「內容被安全阻擋」下方 🗣️ 按鈕專用流程。

    行為：
    - 不刪除任何 Telegram 訊息，包括原本的阻擋提示。
    - 不走一般 🔁 重跑，所以不會刪 AI 訊息。
    - 不重複新增 user 記憶。
    - 要求短期記憶最後一筆必須是 user。
    - 直接用最後一筆 user 記憶作為 source_user_chat_id，重新呼叫 Gemini 補一則 assistant 回覆。
    """
    try:
        gemini_key = get_gemini_key(user_id)
        bot_token = get_bot_token(bot_id)

        if not gemini_key or not bot_token:
            send_message(
                bot_id,
                chat_id,
                f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}"
            )
            return

        recent_rows = list_recent_chat_memory(
            bot_id=bot_id,
            chat_id=chat_id,
            limit=5,
            user_id=user_id,
        )

        if not recent_rows:
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "目前沒有短期記憶可重跑。",
                label="BLOCKED RETRY",
            )
            return

        last = recent_rows[0]
        last_role = str(last.get("role") or "").strip()
        last_text = str(last.get("text") or "").strip()
        last_id = last.get("id")

        print(
            f"BLOCKED RETRY START last_id={last_id} last_role={last_role} len={len(last_text)}",
            flush=True,
        )

        if last_role != "user":
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "最後一筆短期記憶不是使用者訊息，無法用阻擋重跑。",
                label="BLOCKED RETRY",
            )
            return

        if not last_text:
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "最後一筆使用者記憶是空的，無法重跑。",
                label="BLOCKED RETRY",
            )
            return

        _send_generated_reply(
            gemini_key=gemini_key,
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            user_text=last_text,
            source_user_chat_id=last_id,
            label="BLOCKED RETRY",
        )

    except Exception as exc:
        print("BLOCKED RETRY ERROR:", exc, flush=True)
        try:
            send_message(bot_id, chat_id, "執行阻擋重跑時發生錯誤，請看 Render log。")
        except Exception:
            pass

'''

    text = text.replace(marker, func + marker)
    path.write_text(text, encoding="utf-8")
    print("PATCH services/call_ai.py")


def patch_call_handler():
    path = ROOT / "handlers" / "call_handler.py"
    text = path.read_text(encoding="utf-8")

    old_import = "from services.call_ai import run_reply_recovery"
    new_import = "from services.call_ai import run_reply_recovery, run_blocked_reply_retry"
    if new_import not in text:
        if old_import not in text:
            raise RuntimeError("handlers/call_handler.py: cannot find services.call_ai import")
        text = text.replace(old_import, new_import, 1)

    old_block = '''    # =========================
    # 安全阻擋提示按鈕
    # - 使用者點完後先刪除阻擋提示
    # - 再依來源執行重跑 / 接續 / /reply 救援
    # =========================
    if user_text == "blocked_reply_debug":
        delete_message(bot_id, chat_id, message_id)

        answer_callback_query(
            bot_id,
            callback_id,
            text="正在嘗試重跑回覆"
        )

        threading.Thread(
            target=run_reply_recovery,
            args=(user_id, bot_id, chat_id),
            daemon=True,
        ).start()
        return
'''

    new_block = '''    # =========================
    # 安全阻擋提示按鈕
    # - 不刪除阻擋提示訊息
    # - 不走一般 🔁 重跑，避免刪除 AI 訊息
    # - 直接用短期記憶最後一筆 user 重新生成一則 assistant 回覆
    # =========================
    if user_text == "blocked_reply_debug":
        answer_callback_query(
            bot_id,
            callback_id,
            text="正在用最後一筆使用者訊息重跑"
        )

        threading.Thread(
            target=run_blocked_reply_retry,
            args=(user_id, bot_id, chat_id),
            daemon=True,
        ).start()
        return
'''

    if new_block not in text:
        if old_block not in text:
            raise RuntimeError("handlers/call_handler.py: cannot find blocked_reply_debug block")
        text = text.replace(old_block, new_block, 1)

    path.write_text(text, encoding="utf-8")
    print("PATCH handlers/call_handler.py")


def main():
    patch_call_ai()
    patch_call_handler()
    print("DONE blocked retry patch")


if __name__ == "__main__":
    main()
