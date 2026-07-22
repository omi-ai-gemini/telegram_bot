from typing import Any, Dict, Optional
from services.gemini_service import ask_gemini_prompt
from services.style import build_prompt

def generate_reply_by_mode(*, user_id: Any, bot_id: Any, chat_id: Any, gemini_key: Optional[str], history, user_text, emotion, mode="聊天模式", chat_persona_settings=None, character_settings=None, reply_style_settings=None, facts=None, memory_context=None, time_context=None, include_thoughts=True, debug_context=None, model_override=None, stop_event=None) -> Dict[str, Any]:
    prompt = build_prompt(history=history, user_text=user_text, emotion=emotion, mode=mode, chat_persona_settings=chat_persona_settings, character_settings=character_settings, reply_style_settings=reply_style_settings, facts=facts, memory_context=memory_context, time_context=time_context)
    if not gemini_key:
        return {"text": None, "thoughts": "", "thought_source": "empty", "provider": "main", "model": "Gemini", "error": "Gemini API Key 尚未設定", "ok": False}
    result = ask_gemini_prompt(gemini_key=gemini_key, prompt=prompt, include_thoughts=include_thoughts, return_meta=include_thoughts, debug_context=debug_context, prompt_meta={"mode": mode, "history_count": len(history or []), "facts_count": len(facts or []), "provider": "main"})
    if isinstance(result, dict):
        return {"text": result.get("text"), "thoughts": result.get("thoughts", ""), "thought_source": result.get("thought_source", "empty"), "provider": "main", "model": result.get("model") or "Gemini", "ok": bool(result.get("text"))}
    return {"text": result, "thoughts": "", "thought_source": "empty", "provider": "main", "model": "Gemini", "ok": bool(result)}
