from services.ai_actions import (
    build_ai_action_keyboard,
    cache_ai_thought_summary,
    create_ai_message_action,
    update_action_telegram_message_id,
    send_blocked_reply_message,
)
from services.gemini_service import ask_gemini, GEMINI_BLOCKED
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message, edit_message_text
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.reply_style import get_reply_style_settings
from services.user_notice import send_once_user_notice
from services.memory_summary import get_memory_context, maintain_memory_after_reply
from services.time_context import get_current_time_context
import threading

from services.memory import (
    add_chat,
    get_chat,
    get_chat_for_prompt,
    get_facts,
    update_emotion,
    detect_emotion,
    get_emotion,
    list_recent_chat_memory,
)



BLOCKED_REPLY_TEXT = "內容被安全阻擋"

# =========================
# 共用工具
# =========================
def _is_group_chat(chat_id):
    try:
        return int(chat_id) < 0
    except Exception:
        return str(chat_id).startswith("-")


def _extract_telegram_message_id(result):
    if not isinstance(result, dict):
        return None

    message = result.get("result") or {}
    return message.get("message_id")


def _send_ai_message_with_retry(bot_id, chat_id, text, reply_markup=None, label="AI"):
    """
    傳送 AI 訊息，並補上明確 log。

    目的：
    - 追查 Gemini 已回覆但 Telegram 沒收到的狀況。
    - 如果帶 Inline Keyboard 送失敗，立刻改純文字重送一次，避免整則回覆消失。
    """
    text = str(text or "")

    print(
        f"{label} SEND START len={len(text)} has_buttons={bool(reply_markup)}",
        flush=True
    )

    sent = send_message(bot_id, chat_id, text, reply_markup=reply_markup)
    telegram_message_id = _extract_telegram_message_id(sent)

    print(
        f"{label} SEND RESULT ok={bool(telegram_message_id)} "
        f"telegram_message_id={telegram_message_id} raw_ok={bool(sent)}",
        flush=True
    )

    if telegram_message_id or not reply_markup:
        return sent, telegram_message_id

    print(
        f"{label} SEND RETRY without buttons because first send failed",
        flush=True
    )

    retry_sent = send_message(bot_id, chat_id, text, reply_markup=None)
    retry_message_id = _extract_telegram_message_id(retry_sent)

    print(
        f"{label} SEND RETRY RESULT ok={bool(retry_message_id)} "
        f"telegram_message_id={retry_message_id} raw_ok={bool(retry_sent)}",
        flush=True
    )

    return retry_sent, retry_message_id


def _get_generation_settings(bot_id, chat_id, user_id, scope):
    """集中取得 Gemini 回覆所需的設定與上下文。"""
    character_settings = get_character_settings(bot_id, chat_id, user_id=user_id)
    mode = character_settings.get("mode", "聊天模式")

    history = get_chat_for_prompt(bot_id, chat_id, user_id=user_id, mode=mode)
    facts = get_facts(bot_id, chat_id, scope, user_id=user_id, limit=20)
    memory_context = get_memory_context(bot_id, chat_id, scope, user_id=user_id)

    chat_persona_settings = None
    if mode == "聊天模式":
        chat_persona_settings = get_chat_persona_settings(bot_id, chat_id, user_id=user_id)

    reply_style_settings = get_reply_style_settings(
        bot_id=bot_id,
        chat_id=chat_id,
        style_type=mode,
        user_id=user_id,
    )

    time_context = get_current_time_context()

    return {
        "history": history,
        "facts": facts,
        "memory_context": memory_context,
        "character_settings": character_settings,
        "mode": mode,
        "chat_persona_settings": chat_persona_settings,
        "reply_style_settings": reply_style_settings,
        "time_context": time_context,
    }


def _attach_reply_buttons_in_background(
    bot_id,
    chat_id,
    user_id,
    reply_text,
    telegram_message_id,
    assistant_chat_id,
    source_user_chat_id,
    generation_type,
    thought_summary,
    thought_source="empty",
    label="AI",
    show_buttons=True,
):
    """
    背景補掛 AI 操作按鈕與 🧠 推理摘要。

    重要：
    - 主回覆已經送出後才跑這段。
    - 這段任何錯誤都只印 log，不可以影響使用者收到文字回覆。
    - 🧠 thought cache / token / URL / Inline Keyboard 都屬於附加功能。
    """
    if _is_group_chat(chat_id):
        print(f"{label} BUTTON SKIP: group chat", flush=True)
        return

    if not telegram_message_id:
        print(f"{label} BUTTON SKIP: missing telegram_message_id", flush=True)
        return

    def worker():
        action_id = None

        try:
            action_id = create_ai_message_action(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                assistant_chat_id=assistant_chat_id,
                source_user_chat_id=source_user_chat_id,
                context_chat_id=source_user_chat_id,
                generation_type=generation_type,
            )

            print(
                f"{label} ACTION CREATED action_id={action_id} assistant_chat_id={assistant_chat_id} "
                f"source_user_chat_id={source_user_chat_id} type={generation_type}",
                flush=True,
            )

            if not action_id:
                return

            # 先更新 Telegram message id。就算後面按鈕或 thought cache 出錯，
            # 修改/重跑/接續仍有機會靠 action 對到原訊息。
            update_action_telegram_message_id(action_id, telegram_message_id)

            cache_ai_thought_summary(action_id, thought_summary, status=thought_source)

            if not show_buttons:
                print(
                    f"{label} BUTTON HIDDEN action_id={action_id} telegram_message_id={telegram_message_id}",
                    flush=True,
                )
                return

            reply_markup = build_ai_action_keyboard(action_id)

            print(
                f"{label} BUTTON ATTACH START action_id={action_id} telegram_message_id={telegram_message_id}",
                flush=True,
            )

            edited = edit_message_text(
                bot_id,
                chat_id,
                telegram_message_id,
                reply_text,
                reply_markup=reply_markup,
            )

            print(
                f"{label} BUTTON ATTACH RESULT action_id={action_id} ok={bool(edited)}",
                flush=True,
            )

        except Exception as exc:
            print(
                f"{label} BUTTON BACKGROUND ERROR action_id={action_id}: {exc}",
                flush=True,
            )

    threading.Thread(target=worker, daemon=True).start()

def _send_generated_reply(
    gemini_key,
    bot_id,
    chat_id,
    user_id,
    user_text,
    source_user_chat_id,
    label="AI",
):
    """
    對既有 user 記憶產生 AI 回覆。

    用於：
    - 正常 run_ai：source_user_chat_id 是剛寫入的 user 記憶。
    - /reply 救援：source_user_chat_id 是短期記憶最後一筆 user。
    """
    scope = "group" if _is_group_chat(chat_id) else "private"
    emotion = get_emotion(chat_id)
    settings = _get_generation_settings(bot_id, chat_id, user_id, scope)

    gemini_result = ask_gemini(
        gemini_key=gemini_key,
        history=settings["history"],
        user_text=user_text,
        emotion=emotion,
        mode=settings["mode"],
        chat_persona_settings=settings["chat_persona_settings"],
        character_settings=settings["character_settings"],
        reply_style_settings=settings["reply_style_settings"],
        facts=settings["facts"],
        memory_context=settings["memory_context"],
        time_context=settings["time_context"],
        include_thoughts=True,
        return_meta=True,
        debug_context={
            "bot_id": bot_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "source": label,
        },
    )

    if isinstance(gemini_result, dict):
        reply = gemini_result.get("text")
        thought_summary = gemini_result.get("thoughts", "")
        thought_source = gemini_result.get("thought_source", "empty")
    else:
        reply = gemini_result
        thought_summary = ""
        thought_source = "empty"

    if reply == GEMINI_BLOCKED:
        print(f"{label} BLOCKED SEND: Gemini blocked chat reply", flush=True)
        send_blocked_reply_message(bot_id, chat_id)
        return False

    if not reply:
        print(f"{label} SKIP SEND: Gemini returned empty reply", flush=True)
        _send_ai_message_with_retry(bot_id, chat_id, "Gemini 沒有回傳可用文字，請稍後再用 /reply 補一次。", label=label)
        return False

    assistant_chat_id = add_chat(bot_id, chat_id, "assistant", reply, user_id=user_id)

    # 先送文字，按鈕與 🧠 推理摘要全部改成背景補掛。
    # 這樣 thought/cache/button 任何一段炸掉，都不會卡住主要回覆。
    sent, telegram_message_id = _send_ai_message_with_retry(
        bot_id,
        chat_id,
        reply,
        reply_markup=None,
        label=label,
    )

    _attach_reply_buttons_in_background(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        reply_text=reply,
        telegram_message_id=telegram_message_id,
        assistant_chat_id=assistant_chat_id,
        source_user_chat_id=source_user_chat_id,
        generation_type="reply",
        thought_summary=thought_summary,
        thought_source=thought_source,
        label=label,
        show_buttons=settings["mode"] != "聊天模式",
    )

    maintain_memory_after_reply(gemini_key, bot_id, chat_id, user_id=user_id)
    return bool(telegram_message_id or sent)


# =========================
# 正常 AI 回覆流程
# =========================
def run_ai(user_id: int, bot_id: str, chat_id: int, user_text: str, user_message_id=None):

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

        # =========================
        # 全體使用者一次性公告
        # 每個 user + bot 只會收到一次
        # =========================
        send_once_user_notice(user_id, bot_id, chat_id)

        # =========================
        # 先寫入使用者短期記憶
        # 注意：短期記憶不在 add_chat 內直接刪舊資料。
        # 舊資料會在長期摘要成功後才清理。
        # =========================
        user_chat_id = add_chat(
            bot_id,
            chat_id,
            "user",
            user_text,
            user_id=user_id,
            telegram_message_id=user_message_id,
        )

        # =========================
        # 情緒記憶
        # =========================
        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)

        # =========================
        # 一般文字不再觸發「手動記憶」
        # 重點記憶統一從設定中心的「⭐ 重點記憶」寫入 facts_memory。
        # =========================
        _send_generated_reply(
            gemini_key=gemini_key,
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            user_text=user_text,
            source_user_chat_id=user_chat_id,
            label="AI",
        )

    except Exception as e:
        print("AI ERROR:", e, flush=True)
        return


# =========================
# /reply 救援指令
# =========================
def run_reply_recovery(user_id: int, bot_id: str, chat_id: int):
    """
    /reply 救援指令：

    - 如果短期記憶最後一句是 assistant：把最後一句 AI 訊息重送到聊天室。
    - 如果短期記憶最後一句是 user：不重複寫 user 記憶，直接讓 Gemini 補回覆。
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
            limit=20,
            user_id=user_id,
        )

        if not recent_rows:
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "目前沒有短期記憶可救援。",
                label="REPLY RECOVERY",
            )
            return

        last = recent_rows[0]
        last_role = str(last.get("role") or "").strip()
        last_text = str(last.get("text") or "").strip()
        last_id = last.get("id")

        print(
            f"REPLY RECOVERY START last_id={last_id} last_role={last_role} len={len(last_text)}",
            flush=True,
        )

        if not last_text:
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "最後一筆短期記憶是空的，無法救援。",
                label="REPLY RECOVERY",
            )
            return

        # =========================
        # 最後一句是 AI：直接重送最後一筆 AI 記憶。
        # 不新增 chat_memory，避免短期記憶膨脹。
        # =========================
        if last_role == "assistant":
            source_user_chat_id = None

            for row in recent_rows[1:]:
                if str(row.get("role") or "").strip() == "user":
                    source_user_chat_id = row.get("id")
                    break

            # /reply 救援也一樣：先把文字送出去，按鈕背景補掛。
            sent, telegram_message_id = _send_ai_message_with_retry(
                bot_id,
                chat_id,
                last_text,
                reply_markup=None,
                label="REPLY RESEND",
            )

            scope = "group" if _is_group_chat(chat_id) else "private"
            settings = _get_generation_settings(bot_id, chat_id, user_id, scope)

            _attach_reply_buttons_in_background(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                reply_text=last_text,
                telegram_message_id=telegram_message_id,
                assistant_chat_id=last_id,
                source_user_chat_id=source_user_chat_id,
                generation_type="reply_resend",
                thought_summary="",
                label="REPLY RESEND",
                show_buttons=settings["mode"] != "聊天模式",
            )

            print(
                f"REPLY RECOVERY RESEND DONE telegram_message_id={telegram_message_id}",
                flush=True,
            )
            return

        # =========================
        # 最後一句是使用者：不重複寫 user 記憶，直接補 Gemini 回覆。
        # =========================
        if last_role == "user":
            _send_generated_reply(
                gemini_key=gemini_key,
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                user_text=last_text,
                source_user_chat_id=last_id,
                label="REPLY GENERATE",
            )
            return

        _send_ai_message_with_retry(
            bot_id,
            chat_id,
            f"最後一筆短期記憶角色是 {last_role or '未知'}，無法用 /reply 救援。",
            label="REPLY RECOVERY",
        )

    except Exception as exc:
        print("REPLY RECOVERY ERROR:", exc, flush=True)
        try:
            send_message(bot_id, chat_id, "執行 /reply 時發生錯誤，請看 Render log。")
        except Exception:
            pass
