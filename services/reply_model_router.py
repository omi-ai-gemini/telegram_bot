from typing import Any, Dict, Optional

from services.aihorde_text_service import generate_chat_reply, get_secondary_model_label
from services.gemini_service import ask_gemini_prompt
from services.model_mode import MODE_MAIN, MODE_SECONDARY, get_api_model_mode
from services.style import build_prompt


def _normalize_main(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return {
            "text": result.get("text"),
            "thoughts": result.get("thoughts", ""),
            "thought_source": result.get("thought_source", "empty"),
            "provider": MODE_MAIN,
            "model": "Gemini",
            "ok": bool(result.get("text")),
        }

    return {
        "text": result,
        "thoughts": "",
        "thought_source": "empty",
        "provider": MODE_MAIN,
        "model": "Gemini",
        "ok": bool(result),
    }


def _normalize_secondary(result: Any) -> Dict[str, Any]:
    payload = result if isinstance(result, dict) else {}
    return {
        "text": payload.get("text"),
        "thoughts": "本次回覆由 AI Horde 副模型產生，沒有 Gemini 推理摘要。",
        "thought_source": "generated",
        "provider": MODE_SECONDARY,
        "model": payload.get("model") or get_secondary_model_label(),
        "error": payload.get("message") or (None if payload.get("text") else "副模型沒有回傳結果"),
        "request_id": payload.get("request_id"),
        "elapsed": payload.get("elapsed"),
        "ok": bool(payload.get("ok") and payload.get("text")),
        "canceled": bool(payload.get("canceled")),
    }


def generate_reply_by_mode(
    *,
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    gemini_key: Optional[str],
    history,
    user_text,
    emotion,
    mode="聊天模式",
    chat_persona_settings=None,
    character_settings=None,
    reply_style_settings=None,
    facts=None,
    memory_context=None,
    time_context=None,
    include_thoughts=True,
    debug_context=None,
    model_override=None,
    stop_event=None,
) -> Dict[str, Any]:
    """
    所有聊天回覆共用的唯一模型分流節點。

    一般回覆、重跑、接續、/reply、阻擋競速都先完成同一份 Prompt，
    到真正要送出模型的最後一步才依 /modes_api 決定 API。
    """
    selected_mode = model_override or get_api_model_mode(user_id, bot_id, chat_id)
    if selected_mode not in {MODE_MAIN, MODE_SECONDARY}:
        selected_mode = MODE_MAIN

    prompt = build_prompt(
        history=history,
        user_text=user_text,
        emotion=emotion,
        mode=mode,
        chat_persona_settings=chat_persona_settings,
        character_settings=character_settings,
        reply_style_settings=reply_style_settings,
        facts=facts,
        memory_context=memory_context,
        time_context=time_context,
    )

    label = str((debug_context or {}).get("source") or "reply")
    print(
        "MODEL ROUTE FINAL NODE "
        f"label={label} selected={selected_mode} user_id={user_id} bot_id={bot_id} chat_id={chat_id}",
        flush=True,
    )

    if selected_mode == MODE_SECONDARY:
        secondary_debug = dict(debug_context or {})
        secondary_debug["source"] = f"{label}_SECONDARY"
        secondary_debug["generation_type"] = secondary_debug.get("generation_type") or "reply_secondary"
        result = generate_chat_reply(
            prompt=prompt,
            debug_context=secondary_debug,
            stop_event=stop_event,
        )
        return _normalize_secondary(result)

    if not gemini_key:
        return {
            "text": None,
            "thoughts": "",
            "thought_source": "empty",
            "provider": MODE_MAIN,
            "model": "Gemini",
            "error": "Gemini API Key 尚未設定",
            "ok": False,
        }

    result = ask_gemini_prompt(
        gemini_key=gemini_key,
        prompt=prompt,
        include_thoughts=include_thoughts,
        return_meta=include_thoughts,
        debug_context=debug_context,
        prompt_meta={
            "mode": mode,
            "history_count": len(history or []),
            "facts_count": len(facts or []),
            "provider": MODE_MAIN,
        },
    )
    return _normalize_main(result)
