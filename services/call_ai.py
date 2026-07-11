from services.ai_actions import (
    build_ai_action_keyboard,
    cache_ai_thought_summary,
    create_ai_message_action,
    update_action_telegram_message_id,
    send_blocked_reply_message,
)
from services.gemini_service import ask_gemini, GEMINI_BLOCKED
from services.aihorde_text_service import generate_chat_reply, get_secondary_model_label
from services.model_mode import (
    MODE_MAIN,
    MODE_SECONDARY,
    get_api_model_mode,
    set_api_model_mode,
)
from services.style import build_prompt
from services.user_router import get_gemini_key
from services.bot_router import get_bot_token
from services.telegram_service import send_message, edit_message_text, delete_message
from services.character import get_character_settings
from services.chat_persona import get_chat_persona_settings
from services.reply_style import get_reply_style_settings
from services.user_notice import send_once_user_notice
from services.memory_summary import get_memory_context, maintain_memory_after_reply
from services.time_context import get_current_time_context
import queue
import threading
import time

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

def _normalize_generation_result(result, provider):
    if provider == MODE_MAIN:
        if isinstance(result, dict):
            return {
                "text": result.get("text"),
                "thoughts": result.get("thoughts", ""),
                "thought_source": result.get("thought_source", "empty"),
                "provider": MODE_MAIN,
                "model": "Gemini",
            }
        return {
            "text": result,
            "thoughts": "",
            "thought_source": "empty",
            "provider": MODE_MAIN,
            "model": "Gemini",
        }

    return {
        "text": result.get("text") if isinstance(result, dict) else None,
        "thoughts": "本次回覆由 AI Horde 副模型產生，沒有 Gemini 推理摘要。",
        "thought_source": "generated",
        "provider": MODE_SECONDARY,
        "model": (result or {}).get("model") if isinstance(result, dict) else get_secondary_model_label(),
        "error": (result or {}).get("message") if isinstance(result, dict) else "副模型沒有回傳結果",
        "request_id": (result or {}).get("request_id") if isinstance(result, dict) else None,
        "elapsed": (result or {}).get("elapsed") if isinstance(result, dict) else None,
        "ok": bool((result or {}).get("ok")) if isinstance(result, dict) else False,
    }


def _generate_main_reply(
    gemini_key,
    settings,
    user_text,
    emotion,
    user_id,
    bot_id,
    chat_id,
    source_user_chat_id,
    label,
):
    if not gemini_key:
        return {
            "text": None,
            "thoughts": "",
            "thought_source": "empty",
            "provider": MODE_MAIN,
            "model": "Gemini",
            "error": "Gemini API Key 尚未設定",
        }

    result = ask_gemini(
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
            "user_id": user_id,
            "bot_id": bot_id,
            "chat_id": chat_id,
            "source": label,
            "generation_type": "reply",
            "source_user_chat_id": source_user_chat_id,
        },
    )
    return _normalize_generation_result(result, MODE_MAIN)


def _generate_secondary_reply(
    settings,
    user_text,
    emotion,
    user_id,
    bot_id,
    chat_id,
    source_user_chat_id,
    label,
    stop_event=None,
):
    prompt = build_prompt(
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
    )

    result = generate_chat_reply(
        prompt=prompt,
        debug_context={
            "user_id": user_id,
            "bot_id": bot_id,
            "chat_id": chat_id,
            "source": f"{label}_SECONDARY",
            "generation_type": "reply_secondary",
            "source_user_chat_id": source_user_chat_id,
        },
        stop_event=stop_event,
    )
    return _normalize_generation_result(result, MODE_SECONDARY)


def _finalize_generated_reply(
    result,
    gemini_key,
    bot_id,
    chat_id,
    user_id,
    source_user_chat_id,
    settings,
    label,
):
    reply = str(result.get("text") or "").strip()
    provider = result.get("provider") or MODE_MAIN

    if not reply:
        return False

    assistant_chat_id = add_chat(bot_id, chat_id, "assistant", reply, user_id=user_id)
    send_label = f"{label} {provider.upper()}"

    sent, telegram_message_id = _send_ai_message_with_retry(
        bot_id,
        chat_id,
        reply,
        reply_markup=None,
        label=send_label,
    )

    _attach_reply_buttons_in_background(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        reply_text=reply,
        telegram_message_id=telegram_message_id,
        assistant_chat_id=assistant_chat_id,
        source_user_chat_id=source_user_chat_id,
        generation_type=f"reply_{provider}",
        thought_summary=result.get("thoughts", ""),
        thought_source=result.get("thought_source", "empty"),
        label=send_label,
        show_buttons=settings["mode"] != "聊天模式",
    )

    if gemini_key:
        maintain_memory_after_reply(gemini_key, bot_id, chat_id, user_id=user_id)
    else:
        print(
            f"{send_label} MEMORY MAINTENANCE SKIP: missing Gemini key",
            flush=True,
        )

    print(
        "MODEL REPLY FINALIZED "
        f"provider={provider} model={result.get('model')} response_chars={len(reply)} "
        f"telegram_message_id={telegram_message_id}",
        flush=True,
    )
    return bool(telegram_message_id or sent)


def _send_generated_reply(
    gemini_key,
    bot_id,
    chat_id,
    user_id,
    user_text,
    source_user_chat_id,
    label="AI",
    model_override=None,
):
    """依目前 /modes_api 狀態，用 Gemini 或 AI Horde 副模型產生回覆。"""
    scope = "group" if _is_group_chat(chat_id) else "private"
    emotion = get_emotion(chat_id)
    settings = _get_generation_settings(bot_id, chat_id, user_id, scope)
    selected_mode = model_override or get_api_model_mode(user_id, bot_id, chat_id)

    print(
        "MODEL ROUTE "
        f"label={label} selected={selected_mode} user_id={user_id} bot_id={bot_id} chat_id={chat_id}",
        flush=True,
    )

    if selected_mode == MODE_SECONDARY:
        result = _generate_secondary_reply(
            settings=settings,
            user_text=user_text,
            emotion=emotion,
            user_id=user_id,
            bot_id=bot_id,
            chat_id=chat_id,
            source_user_chat_id=source_user_chat_id,
            label=label,
        )
        if not result.get("text"):
            message = result.get("error") or "副模型沒有回傳可用文字"
            print(f"{label} SECONDARY EMPTY/ERROR: {message}", flush=True)
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                f"副模型沒有產生可用回覆：{message}",
                label=f"{label} SECONDARY",
            )
            return False
        return _finalize_generated_reply(
            result=result,
            gemini_key=gemini_key,
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            source_user_chat_id=source_user_chat_id,
            settings=settings,
            label=label,
        )

    result = _generate_main_reply(
        gemini_key=gemini_key,
        settings=settings,
        user_text=user_text,
        emotion=emotion,
        user_id=user_id,
        bot_id=bot_id,
        chat_id=chat_id,
        source_user_chat_id=source_user_chat_id,
        label=label,
    )

    if result.get("text") == GEMINI_BLOCKED:
        print(f"{label} BLOCKED SEND: Gemini blocked chat reply", flush=True)
        send_blocked_reply_message(bot_id, chat_id)
        return False

    if not result.get("text"):
        print(f"{label} SKIP SEND: Gemini returned empty reply", flush=True)
        _send_ai_message_with_retry(
            bot_id,
            chat_id,
            "Gemini 沒有回傳可用文字，請按安全阻擋按鈕或用 /reply 補一次。",
            label=label,
        )
        return False

    return _finalize_generated_reply(
        result=result,
        gemini_key=gemini_key,
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        source_user_chat_id=source_user_chat_id,
        settings=settings,
        label=label,
    )


# =========================
# 正常 AI 回覆流程
# =========================
def run_ai(user_id: int, bot_id: str, chat_id: int, user_text: str, user_message_id=None):
    try:
        selected_mode = get_api_model_mode(user_id, bot_id, chat_id)
        gemini_key = get_gemini_key(user_id)
        bot_token = get_bot_token(bot_id)

        if not bot_token or (selected_mode == MODE_MAIN and not gemini_key):
            send_message(
                bot_id,
                chat_id,
                f"設定資訊:\nchat_id={chat_id}\nbot_id={bot_id}\nuser_id={user_id}"
            )
            return

        send_once_user_notice(user_id, bot_id, chat_id)

        user_chat_id = add_chat(
            bot_id,
            chat_id,
            "user",
            user_text,
            user_id=user_id,
            telegram_message_id=user_message_id,
        )

        delta = detect_emotion(user_text)
        update_emotion(chat_id, delta)

        _send_generated_reply(
            gemini_key=gemini_key,
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            user_text="",
            source_user_chat_id=user_chat_id,
            label="AI",
            model_override=selected_mode,
        )

    except Exception as exc:
        print("AI ERROR:", exc, flush=True)
        try:
            send_message(bot_id, chat_id, "回覆流程發生錯誤，請查看 Render log。")
        except Exception:
            pass


# =========================
# 安全阻擋提示按鈕：直接用最後一筆 user 記憶補生回覆
# =========================
def _delete_status_later(bot_id, chat_id, message_id, delay=4):
    if not message_id:
        return

    def worker():
        time.sleep(delay)
        try:
            delete_message(bot_id, chat_id, message_id)
        except Exception as exc:
            print("MODEL RACE STATUS DELETE ERROR:", exc, flush=True)

    threading.Thread(target=worker, daemon=True).start()


def run_blocked_reply_race(user_id: int, bot_id: str, chat_id: int):
    """
    安全阻擋按鈕專用：
    1. 將後續一般回覆模式切成副模型。
    2. 本次同時送 Gemini 與 AI Horde。
    3. 第一個有效回覆勝出，副模型輸掉時會嘗試取消 Horde 任務。
    """
    race_started = time.monotonic()
    status_message_id = None

    try:
        bot_token = get_bot_token(bot_id)
        gemini_key = get_gemini_key(user_id)
        if not bot_token:
            send_message(bot_id, chat_id, "找不到 Telegram Bot Token，無法執行競速。")
            return

        set_api_model_mode(user_id, bot_id, chat_id, MODE_SECONDARY)

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
                "目前沒有短期記憶可競速重跑。",
                label="MODEL RACE",
            )
            return

        last = recent_rows[0]
        last_role = str(last.get("role") or "").strip()
        last_text = str(last.get("text") or "").strip()
        last_id = last.get("id")
        if last_role != "user" or not last_text:
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "最後一筆短期記憶不是有效的使用者訊息，無法競速重跑。",
                label="MODEL RACE",
            )
            return

        status_sent = send_message(
            bot_id,
            chat_id,
            "已切換為副模型，主副模型競速中。",
        )
        status_message_id = _extract_telegram_message_id(status_sent)

        scope = "group" if _is_group_chat(chat_id) else "private"
        emotion = get_emotion(chat_id)
        settings = _get_generation_settings(bot_id, chat_id, user_id, scope)
        results = queue.Queue()
        stop_event = threading.Event()

        print(
            "MODEL RACE START "
            f"user_id={user_id} bot_id={bot_id} chat_id={chat_id} source_user_chat_id={last_id} "
            f"gemini_enabled={bool(gemini_key)} secondary_models={get_secondary_model_label()}",
            flush=True,
        )

        def run_main_branch():
            branch_started = time.monotonic()
            try:
                result = _generate_main_reply(
                    gemini_key=gemini_key,
                    settings=settings,
                    user_text="",
                    emotion=emotion,
                    user_id=user_id,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    source_user_chat_id=last_id,
                    label="BLOCKED_RACE_MAIN",
                )
                results.put((MODE_MAIN, result, time.monotonic() - branch_started))
            except Exception as exc:
                results.put((MODE_MAIN, {"text": None, "error": str(exc), "provider": MODE_MAIN}, time.monotonic() - branch_started))

        def run_secondary_branch():
            branch_started = time.monotonic()
            try:
                result = _generate_secondary_reply(
                    settings=settings,
                    user_text="",
                    emotion=emotion,
                    user_id=user_id,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    source_user_chat_id=last_id,
                    label="BLOCKED_RACE_SECONDARY",
                    stop_event=stop_event,
                )
                results.put((MODE_SECONDARY, result, time.monotonic() - branch_started))
            except Exception as exc:
                results.put((MODE_SECONDARY, {"text": None, "error": str(exc), "provider": MODE_SECONDARY}, time.monotonic() - branch_started))

        branches = 1
        if gemini_key:
            branches += 1
            threading.Thread(target=run_main_branch, daemon=True).start()
        threading.Thread(target=run_secondary_branch, daemon=True).start()

        failures = []
        winner = None
        deadline = time.monotonic() + 165

        for _ in range(branches):
            remaining = max(0.1, deadline - time.monotonic())
            try:
                provider, result, branch_elapsed = results.get(timeout=remaining)
            except queue.Empty:
                failures.append("主副模型競速超時")
                break

            text = str(result.get("text") or "").strip()
            valid = bool(text) and text != GEMINI_BLOCKED
            print(
                "MODEL RACE BRANCH RESULT "
                f"provider={provider} valid={valid} blocked={text == GEMINI_BLOCKED} "
                f"response_chars={len(text)} elapsed={branch_elapsed:.2f} "
                f"error={str(result.get('error') or '')[:200]}",
                flush=True,
            )

            if valid:
                winner = result
                stop_event.set()
                break

            failures.append(
                f"{provider}: " + (
                    "安全阻擋" if text == GEMINI_BLOCKED else str(result.get("error") or "沒有可用文字")
                )
            )

        if not winner:
            if status_message_id:
                edit_message_text(
                    bot_id,
                    chat_id,
                    status_message_id,
                    "主副模型都沒有產生可用回覆。",
                )
            _send_ai_message_with_retry(
                bot_id,
                chat_id,
                "競速失敗：" + "；".join(failures)[:800],
                label="MODEL RACE",
            )
            return

        provider = winner.get("provider") or MODE_SECONDARY
        elapsed = time.monotonic() - race_started
        print(
            "MODEL RACE WINNER "
            f"provider={provider} model={winner.get('model')} elapsed={elapsed:.2f}",
            flush=True,
        )

        if status_message_id:
            edit_message_text(
                bot_id,
                chat_id,
                status_message_id,
                f"競速完成，採用{'副模型' if provider == MODE_SECONDARY else '主模型'}回覆。",
            )
            _delete_status_later(bot_id, chat_id, status_message_id)

        _finalize_generated_reply(
            result=winner,
            gemini_key=gemini_key,
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            source_user_chat_id=last_id,
            settings=settings,
            label="MODEL RACE",
        )

    except Exception as exc:
        print("MODEL RACE ERROR:", exc, flush=True)
        try:
            if status_message_id:
                edit_message_text(bot_id, chat_id, status_message_id, "主副模型競速發生錯誤。")
            else:
                send_message(bot_id, chat_id, "主副模型競速發生錯誤，請查看 Render log。")
        except Exception:
            pass


# 舊名稱保留相容，實際行為已改為切副模型並競速。
def run_blocked_reply_retry(user_id: int, bot_id: str, chat_id: int):
    return run_blocked_reply_race(user_id, bot_id, chat_id)


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

        selected_mode = get_api_model_mode(user_id, bot_id, chat_id)
        if not bot_token or (selected_mode == MODE_MAIN and not gemini_key):
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
                user_text="",
                source_user_chat_id=last_id,
                label="REPLY GENERATE",
                model_override=selected_mode,
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
