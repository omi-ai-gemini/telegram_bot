import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from services.prompt_debug import save_prompt_debug_log, update_prompt_debug_log


AI_HORDE_BASE_URL = os.getenv("AI_HORDE_BASE_URL", "https://aihorde.net/api/v2").rstrip("/")
AI_HORDE_TEXT_CLIENT_AGENT = os.getenv(
    "AI_HORDE_TEXT_CLIENT_AGENT",
    "TeleminiAI:1.0:telegram-secondary-text",
)
AI_HORDE_TEXT_MODELS = [
    item.strip()
    for item in os.getenv(
        "AI_HORDE_TEXT_MODELS",
        "koboldcpp/L3-8B-Stheno-v3.2,koboldcpp/mini-magnum-12b-v1.1",
    ).split(",")
    if item.strip()
]
AI_HORDE_TEXT_TIMEOUT_SECONDS = max(
    20,
    int(os.getenv("AI_HORDE_TEXT_TIMEOUT_SECONDS", "150")),
)
AI_HORDE_TEXT_POLL_SECONDS = max(
    1,
    int(os.getenv("AI_HORDE_TEXT_POLL_SECONDS", "2")),
)
AI_HORDE_TEXT_MAX_CONTEXT = max(
    4096,
    int(os.getenv("AI_HORDE_TEXT_MAX_CONTEXT", "16384")),
)

_SESSION = requests.Session()


def _keys() -> List[Tuple[int, str]]:
    values: List[Tuple[int, str]] = []
    for slot in (1, 2):
        key = str(os.getenv(f"AI_HORDE_API_KEY_{slot}") or "").strip()
        if key:
            values.append((slot, key))
    return values


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Client-Agent": AI_HORDE_TEXT_CLIENT_AGENT,
        "Content-Type": "application/json",
    }
    if api_key:
        headers["apikey"] = api_key
    return headers


def _json_or_error(res: requests.Response) -> Dict[str, Any]:
    try:
        return res.json()
    except Exception:
        return {"message": (res.text or "")[:500]}


def _error_message(payload: Dict[str, Any], status_code: int) -> str:
    return str(
        payload.get("message")
        or payload.get("error")
        or payload.get("reason")
        or f"HTTP {status_code}"
    )


def get_secondary_model_label() -> str:
    return ",".join(AI_HORDE_TEXT_MODELS)



def _clean_generated_text(text: Any) -> str:
    value = str(text or "").strip()
    for token in ("<|eot_id|>", "<|end_of_text|>", "<|start_header_id|>", "<|end_header_id|>"):
        value = value.replace(token, "")
    if value.startswith("```") and value.endswith("```"):
        value = value[3:-3].strip()
    if value.lower().startswith("json\n"):
        value = value[5:].strip()
    for prefix in ("assistant:", "Assistant:", "AI:", "回覆：", "回答："):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    return value


def _llama3_prompt(system_text: str, user_text: str) -> str:
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        + str(system_text or "").strip()
        + "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        + str(user_text or "").strip()
        + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def submit_text_request(
    prompt: str,
    purpose: str,
    max_length: int,
    temperature: float = 0.75,
) -> Dict[str, Any]:
    keys = _keys()
    if not keys:
        return {
            "ok": False,
            "message": "尚未設定 AI_HORDE_API_KEY_1 / AI_HORDE_API_KEY_2",
        }

    models = AI_HORDE_TEXT_MODELS
    if not models:
        return {"ok": False, "message": "AI_HORDE_TEXT_MODELS 未設定"}

    prompt = str(prompt or "")
    if not prompt.strip():
        return {"ok": False, "message": "副模型 Prompt 為空"}
    payload = {
        "prompt": prompt,
        "params": {
            "n": 1,
            "max_context_length": AI_HORDE_TEXT_MAX_CONTEXT,
            "max_length": max(32, int(max_length)),
            "temperature": float(temperature),
            "top_p": 0.92,
            "top_k": 40,
            "tfs": 1,
            "typical": 1,
            "rep_pen": 1.08,
            "rep_pen_range": 1024,
            "singleline": False,
            "frmttriminc": True,
        },
        "models": models,
        "trusted_workers": False,
        "slow_workers": True,
        "extra_slow_workers": True,
    }

    print(
        "SECONDARY TEXT SUBMIT PREPARED "
        f"purpose={purpose} prompt_chars={len(prompt)} max_context={AI_HORDE_TEXT_MAX_CONTEXT} "
        f"max_length={max_length} models={models}",
        flush=True,
    )

    last_error = "AI Horde 副模型送出失敗"
    for index, (slot, key) in enumerate(keys):
        try:
            res = _SESSION.post(
                f"{AI_HORDE_BASE_URL}/generate/text/async",
                headers=_headers(key),
                json=payload,
                timeout=45,
            )
        except Exception as exc:
            last_error = f"AI Horde 副模型連線失敗：{exc}"
            if index + 1 < len(keys):
                continue
            return {"ok": False, "message": last_error}

        data = _json_or_error(res)
        if res.ok and data.get("id"):
            request_id = str(data.get("id"))
            print(
                "SECONDARY TEXT SUBMIT OK "
                f"purpose={purpose} request_id={request_id} api_slot={slot} "
                f"kudos={data.get('kudos')}",
                flush=True,
            )
            return {
                "ok": True,
                "request_id": request_id,
                "api_slot": slot,
                "kudos": data.get("kudos"),
                "warnings": data.get("warnings") or [],
                "prompt_chars": len(prompt),
                "max_context_length": AI_HORDE_TEXT_MAX_CONTEXT,
            }

        last_error = _error_message(data, res.status_code)
        retryable = res.status_code in {401, 403, 429, 500, 502, 503, 504}
        print(
            "SECONDARY TEXT SUBMIT ERROR "
            f"purpose={purpose} api_slot={slot} status={res.status_code} reason={last_error[:300]}",
            flush=True,
        )
        if not retryable or index + 1 >= len(keys):
            return {
                "ok": False,
                "message": last_error,
                "status_code": res.status_code,
            }

    return {"ok": False, "message": last_error}


def get_text_status(request_id: str, api_slot: Optional[int] = None) -> Dict[str, Any]:
    key = dict(_keys()).get(int(api_slot or 0))
    try:
        res = _SESSION.get(
            f"{AI_HORDE_BASE_URL}/generate/text/status/{request_id}",
            headers=_headers(key),
            timeout=35,
        )
        data = _json_or_error(res)
        if not res.ok:
            return {
                "ok": False,
                "message": _error_message(data, res.status_code),
                "status_code": res.status_code,
            }
        data["ok"] = True
        return data
    except Exception as exc:
        return {"ok": False, "message": f"查詢副模型狀態失敗：{exc}"}


def cancel_text_request(request_id: str, api_slot: Optional[int] = None) -> bool:
    key = dict(_keys()).get(int(api_slot or 0))
    try:
        res = _SESSION.delete(
            f"{AI_HORDE_BASE_URL}/generate/text/status/{request_id}",
            headers=_headers(key),
            timeout=30,
        )
        print(
            f"SECONDARY TEXT CANCEL request_id={request_id} ok={res.ok}",
            flush=True,
        )
        return bool(res.ok)
    except Exception as exc:
        print("SECONDARY TEXT CANCEL ERROR:", exc, flush=True)
        return False


def generate_text(
    prompt: str,
    purpose: str,
    max_length: int,
    temperature: float = 0.75,
    timeout_seconds: Optional[int] = None,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    started = time.monotonic()
    if stop_event is not None and stop_event.is_set():
        return {
            "ok": False,
            "canceled": True,
            "message": "副模型競速已由另一模型先完成",
        }

    submitted = submit_text_request(
        prompt=prompt,
        purpose=purpose,
        max_length=max_length,
        temperature=temperature,
    )
    if not submitted.get("ok"):
        return submitted

    request_id = submitted.get("request_id")
    api_slot = submitted.get("api_slot")
    timeout_seconds = max(10, int(timeout_seconds or AI_HORDE_TEXT_TIMEOUT_SECONDS))
    last_queue_position = None
    last_wait_time = None

    while time.monotonic() - started < timeout_seconds:
        if stop_event is not None and stop_event.is_set():
            cancel_text_request(request_id, api_slot)
            return {
                "ok": False,
                "canceled": True,
                "message": "副模型競速已由另一模型先完成",
                "request_id": request_id,
                "api_slot": api_slot,
            }

        status = get_text_status(request_id, api_slot)
        if not status.get("ok"):
            if status.get("status_code") == 404:
                return {
                    "ok": False,
                    "message": "AI Horde 找不到副模型任務",
                    "request_id": request_id,
                    "api_slot": api_slot,
                }
            time.sleep(AI_HORDE_TEXT_POLL_SECONDS)
            continue

        queue_position = status.get("queue_position")
        wait_time = status.get("wait_time")
        if queue_position != last_queue_position or wait_time != last_wait_time:
            print(
                "SECONDARY TEXT STATUS "
                f"purpose={purpose} request_id={request_id} done={status.get('done')} "
                f"waiting={status.get('waiting')} processing={status.get('processing')} "
                f"queue_position={queue_position} wait_time={wait_time}",
                flush=True,
            )
            last_queue_position = queue_position
            last_wait_time = wait_time

        if status.get("faulted"):
            return {
                "ok": False,
                "message": "AI Horde 副模型任務異常",
                "request_id": request_id,
                "api_slot": api_slot,
            }

        if status.get("is_possible") is False:
            return {
                "ok": False,
                "message": "目前沒有可執行副模型的工作節點",
                "request_id": request_id,
                "api_slot": api_slot,
            }

        generations = status.get("generations") or []
        if status.get("done") or generations:
            for generation in generations:
                text = _clean_generated_text(generation.get("text"))
                if text:
                    elapsed = round(time.monotonic() - started, 2)
                    print(
                        "SECONDARY TEXT DONE "
                        f"purpose={purpose} request_id={request_id} model={generation.get('model')} "
                        f"worker={generation.get('worker_name')} response_chars={len(text)} "
                        f"elapsed={elapsed}",
                        flush=True,
                    )
                    return {
                        "ok": True,
                        "text": text,
                        "model": generation.get("model") or get_secondary_model_label(),
                        "worker_name": generation.get("worker_name"),
                        "worker_id": generation.get("worker_id"),
                        "request_id": request_id,
                        "api_slot": api_slot,
                        "elapsed": elapsed,
                        "queue_position": queue_position,
                        "wait_time": wait_time,
                    }

            return {
                "ok": False,
                "message": "副模型完成但沒有回傳文字",
                "request_id": request_id,
                "api_slot": api_slot,
            }

        time.sleep(AI_HORDE_TEXT_POLL_SECONDS)

    cancel_text_request(request_id, api_slot)
    return {
        "ok": False,
        "timeout": True,
        "message": f"副模型等待超過 {timeout_seconds} 秒",
        "request_id": request_id,
        "api_slot": api_slot,
    }


def _save_secondary_debug(
    prompt: str,
    purpose: str,
    debug_context: Optional[Dict[str, Any]],
) -> Optional[int]:
    if not debug_context:
        return None
    try:
        return save_prompt_debug_log(
            prompt_text=prompt,
            user_id=debug_context.get("user_id"),
            bot_id=debug_context.get("bot_id"),
            chat_id=debug_context.get("chat_id"),
            source=debug_context.get("source", "secondary"),
            generation_type=debug_context.get("generation_type", purpose),
            action_id=debug_context.get("action_id"),
            source_user_chat_id=debug_context.get("source_user_chat_id"),
            model=get_secondary_model_label(),
            prompt_meta={
                "provider": "ai_horde",
                "purpose": purpose,
                "models": AI_HORDE_TEXT_MODELS,
            },
        )
    except Exception as exc:
        print("SECONDARY PROMPT DEBUG SAVE SKIPPED:", exc, flush=True)
        return None


def generate_chat_reply(
    prompt: str,
    debug_context: Optional[Dict[str, Any]] = None,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    secondary_prompt = _llama3_prompt(
        system_text="""
你是 Telemini 的副回覆模型。
直接依照使用者提供的人物、記憶、模式與風格完成回覆。
使用繁體中文，不要提到模型、提示詞、規則或資料庫。
不要輸出測試確認句，只輸出真正要傳給使用者看的回覆。
""",
        user_text=str(prompt or "") + """

【副模型最終輸出規則】
- 直接回覆近期對話最後一則使用者訊息。
- 必須遵守人物、模式、記憶與回覆風格。
- 不要回答任何要求你只回覆測試確認句的舊指令。
- 只輸出回覆本體，不加標題。
""",
    )

    debug_id = _save_secondary_debug(secondary_prompt, "chat_reply", debug_context)
    result = generate_text(
        prompt=secondary_prompt,
        purpose="chat_reply",
        max_length=int(os.getenv("AI_HORDE_CHAT_MAX_LENGTH", "320")),
        temperature=float(os.getenv("AI_HORDE_CHAT_TEMPERATURE", "0.82")),
        stop_event=stop_event,
    )

    if debug_id:
        try:
            update_prompt_debug_log(
                debug_id,
                status="ok" if result.get("ok") else ("canceled" if result.get("canceled") else "error"),
                block_reason="" if result.get("ok") else str(result.get("message") or "")[:500],
                response_chars=len(result.get("text") or ""),
            )
        except Exception as exc:
            print("SECONDARY PROMPT DEBUG UPDATE SKIPPED:", exc, flush=True)

    return result


def organize_image_prompt(
    draft_prompt: str,
    generation_mode: str,
    debug_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    positive, separator, negative = str(draft_prompt or "").partition(" ### ")
    mode_name = "img2img" if str(generation_mode) == "image" else "txt2img"

    organizer_prompt = _llama3_prompt(
        system_text="""
You compile user requests into precise diffusion-image prompts.
Return only one English positive prompt with no explanation or markdown.
""",
        user_text=f"""
Task mode: {mode_name}

Convert the source request below into one concise, concrete English positive prompt.
Rules:
- Preserve every explicit person, clothing, pose, action, object, camera, scene, lighting, and identity requirement.
- Translate Chinese visual descriptions into direct English visual instructions.
- Resolve wording into visible image details instead of story narration.
- Do not remove adult sensual details that are explicitly requested.
- Do not add new people, new objects, or new story events.
- For img2img, clearly state what must change while preserving the source person's recognizable identity unless the request says otherwise.
- Return only the final English positive prompt.
- No explanation, no title, no markdown, no negative prompt.

SOURCE REQUEST:
{positive.strip()}
""",
    )

    debug_id = _save_secondary_debug(organizer_prompt, "image_prompt", debug_context)
    result = generate_text(
        prompt=organizer_prompt,
        purpose="image_prompt",
        max_length=int(os.getenv("AI_HORDE_IMAGE_PROMPT_MAX_LENGTH", "360")),
        temperature=float(os.getenv("AI_HORDE_IMAGE_PROMPT_TEMPERATURE", "0.55")),
        timeout_seconds=int(os.getenv("AI_HORDE_IMAGE_PROMPT_TIMEOUT_SECONDS", "120")),
    )

    if result.get("ok"):
        organized = _clean_generated_text(result.get("text"))
        for prefix in ("POSITIVE:", "Positive:", "FINAL PROMPT:", "Final prompt:"):
            if organized.startswith(prefix):
                organized = organized[len(prefix):].strip()
                break
        organized = organized.split("###", 1)[0].strip().strip('"')
        for marker in ("Negative prompt:", "NEGATIVE:", "Negative:"):
            if marker in organized:
                organized = organized.split(marker, 1)[0].strip()

        if len(organized) < 20:
            result = {
                **result,
                "ok": False,
                "message": "副模型整理後提示詞過短",
            }
        else:
            result["text"] = organized + (f" ### {negative.strip()}" if separator and negative.strip() else "")

    if debug_id:
        try:
            update_prompt_debug_log(
                debug_id,
                status="ok" if result.get("ok") else "error",
                block_reason="" if result.get("ok") else str(result.get("message") or "")[:500],
                response_chars=len(result.get("text") or ""),
            )
        except Exception as exc:
            print("IMAGE PROMPT DEBUG UPDATE SKIPPED:", exc, flush=True)

    return result
