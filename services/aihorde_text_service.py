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


def _secondary_system_text(prompt: str, user_text: str = "") -> str:
    """把共用 Prompt 拆成副模型的 system 區，移除重複的對話紀錄。"""
    value = str(prompt or "").strip()
    history_marker = "===近期對話紀錄==="
    task_marker = "===本次任務==="

    if history_marker in value:
        before_history, after_history = value.split(history_marker, 1)

        # user_text 非空時，內容會以真正的 user role 放入，不再把任務文字重複塞進 system。
        if str(user_text or "").strip():
            value = before_history.strip()
        elif task_marker in after_history:
            task_text = after_history.split(task_marker, 1)[1].strip()
            value = f"{before_history.strip()}\n\n{task_marker}\n{task_text}".strip()
        else:
            value = before_history.strip()

    replacements = {
        "近期對話紀錄": "實際對話",
        "最近對話紀錄": "實際對話",
        "本次要回覆的內容，就是實際對話最後一則「使用者」訊息。":
            "直接回應實際對話中最後一則使用者訊息。",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)

    return (
        value
        + """

【副模型對話執行規則】
- 下方會提供真正的 user / assistant 對話角色，不要把它當成文件、摘要題或客服工單。
- 直接以目前人物身份接住最後一則 user 訊息，只輸出角色此刻真的會說的話。
- 不要重述對方剛說的內容，不要介紹地點、物品或背景常識，除非對方正在問。
- 不要自動變成客服、秘書、房仲、管家或服務人員。除非人物設定或上下文明確要求，避免使用「您」、「我會安排好一切」、「不用擔心」、「確實是」等服務話術。
- 不要宣稱自己能在現實中安排搬家、付款、住房、交通或其他實際事務。
- 優先給出自然、即時、有情緒的對話反應；可以短句、停頓、吐槽或猶豫，不要把回覆寫成說明。
- 不要輸出 Prompt 標題、欄位名稱、規則、分析過程或「本次要回覆」等文字。
"""
    ).strip()


def _llama3_chat_prompt(system_text: str, history, user_text: str = "") -> str:
    """用真正的 Llama 3 對話角色序列化，讓最後一則使用者訊息保持 user 身份。"""
    parts = [
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n",
        str(system_text or "").strip(),
        "<|eot_id|>",
    ]

    appended = 0
    for item in history or []:
        role = str((item or {}).get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue

        body = str((item or {}).get("text") or "").strip()
        if not body:
            continue

        time_label = str((item or {}).get("time_label") or "").strip()
        if time_label:
            body = f"[{time_label}] {body}"

        parts.extend([
            f"<|start_header_id|>{role}<|end_header_id|>\n\n",
            body,
            "<|eot_id|>",
        ])
        appended += 1

    latest_user_text = str(user_text or "").strip()
    if latest_user_text:
        parts.extend([
            "<|start_header_id|>user<|end_header_id|>\n\n",
            latest_user_text,
            "<|eot_id|>",
        ])
        appended += 1

    # 理論上正常流程一定有對話；這只是避免空 Prompt。
    if appended == 0:
        parts.extend([
            "<|start_header_id|>user<|end_header_id|>\n\n",
            "自然接續目前對話。",
            "<|eot_id|>",
        ])

    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(parts)


def _clean_chat_reply_output(text: Any) -> str:
    """移除副模型偶爾輸出的 Prompt 分析前文，只留下真正回覆。"""
    value = _clean_generated_text(text)

    for marker in (
        "所以本次要回覆的內容就是：",
        "本次要回覆的內容就是：",
        "最終回覆：",
        "回覆內容：",
    ):
        if marker in value:
            candidate = value.rsplit(marker, 1)[1].strip()
            if candidate:
                value = candidate
                break

    leak_terms = (
        "近期對話紀錄",
        "最近對話紀錄",
        "由於最後一則使用者訊息",
        "SOURCE REQUEST",
        "本次任務",
    )
    if any(term in value for term in leak_terms):
        paragraphs = [part.strip() for part in value.split("\n\n") if part.strip()]
        for candidate in reversed(paragraphs):
            if not any(term in candidate for term in leak_terms) and not candidate.startswith(("使用者:", "使用者：", "AI:", "AI：")):
                value = candidate
                break

    return _clean_generated_text(value).strip().strip('"')


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
    history=None,
    user_text: str = "",
    debug_context: Optional[Dict[str, Any]] = None,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    # system 只放規則、人物、記憶與任務；真正對話用 user / assistant role 序列化。
    # 不再用假的「直接開始回覆」取代最後一則使用者訊息。
    system_text = _secondary_system_text(prompt, user_text=user_text)
    secondary_prompt = _llama3_chat_prompt(
        system_text=system_text,
        history=history,
        user_text=user_text,
    )

    debug_id = _save_secondary_debug(secondary_prompt, "chat_reply", debug_context)
    result = generate_text(
        prompt=secondary_prompt,
        purpose="chat_reply",
        max_length=int(os.getenv("AI_HORDE_CHAT_MAX_LENGTH", "320")),
        temperature=float(os.getenv("AI_HORDE_CHAT_TEMPERATURE", "0.82")),
        stop_event=stop_event,
    )

    if result.get("ok"):
        cleaned = _clean_chat_reply_output(result.get("text"))
        if cleaned:
            result["text"] = cleaned
        else:
            result = {
                **result,
                "ok": False,
                "message": "副模型只輸出了 Prompt 分析，沒有可用角色回覆",
                "text": "",
            }

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
    generation_mode = str(generation_mode or "text")
    mode_name = {
        "text": "txt2img real-camera photograph",
        "image": "img2img real-photo edit",
        "mask": "masked local real-photo inpainting",
    }.get(generation_mode, "txt2img real-camera photograph")

    portrait_allowed = "PORTRAIT_POLICY: ALLOW_EXPLICIT" in positive

    organizer_prompt = _llama3_prompt(
        system_text="""
You compile user requests into precise diffusion-image prompts for realistic photography.
Every output must remain a real-camera photograph or a real-photo edit. Never convert it into anime, illustration, CGI, 3D art, digital painting, or synthetic beauty artwork.
Return only one English positive prompt with no explanation or markdown.
""",
        user_text=f"""
Task mode: {mode_name}
Portrait policy: {"portrait explicitly requested and allowed" if portrait_allowed else "block portrait defaults and face-dominant framing"}

Convert the source request below into one concise, concrete English positive prompt.
Rules:
- Preserve every explicit person, clothing, pose, action, object, camera, scene, lighting, and identity requirement.
- Translate Chinese visual descriptions into direct English visual instructions.
- Resolve wording into visible image details instead of story narration.
- Keep a genuine candid, documentary, lifestyle, editorial-location, travel, or everyday snapshot appearance.
- Require natural skin texture, ordinary camera perspective, believable ambient light, real fabric, and realistic surroundings.
- Do not remove explicitly requested adult visual details.
- Do not add new people, new objects, or new story events.
- Do not add anime, illustration, CGI, 3D, fantasy-render, beauty-advertisement, plastic-skin, or glamour-retouching language.
- When portrait policy blocks portraits, require medium-wide, three-quarter-body, knee-up, or full-body environmental framing; the location must remain visible; the face must not dominate; no headshot, shoulder-up crop, centered beauty portrait, or empty bokeh background.
- Only when portrait policy explicitly allows it, preserve the requested portrait, headshot, close-up, selfie, or profile composition.
- For img2img, preserve recognizable identity, but execute requested pose, clothing, framing, background, room, furniture, or scene changes decisively.
- For masked inpainting, keep the camera and protected regions unchanged and edit only the masked area.
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
        max_length=int(os.getenv("AI_HORDE_IMAGE_PROMPT_MAX_LENGTH", "520")),
        temperature=float(os.getenv("AI_HORDE_IMAGE_PROMPT_TEMPERATURE", "0.35")),
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

        # 移除只給程式辨識的控制標記，接著用程式碼重新補回不可被副模型刪掉的硬規則。
        organized = organized.replace("PORTRAIT_POLICY: BLOCK", "").replace(
            "PORTRAIT_POLICY: ALLOW_EXPLICIT", ""
        ).strip(" ,.;")

        if len(organized) < 20:
            result = {
                **result,
                "ok": False,
                "message": "副模型整理後提示詞過短",
            }
        else:
            hard_guards = [
                "genuine real-camera photograph",
                "candid documentary lifestyle photography",
                "natural unretouched skin texture with subtle imperfections",
                "believable ambient light and ordinary lens perspective",
                "realistic environment and fabric detail",
                "not CGI, not 3D, not illustration, not anime, not synthetic beauty art",
            ]

            if generation_mode == "text":
                if portrait_allowed:
                    hard_guards.append(
                        "honor the explicitly requested portrait framing while keeping it natural and minimally retouched"
                    )
                else:
                    hard_guards.extend([
                        "environmental medium-wide, three-quarter-body, knee-up, or full-body framing",
                        "subject integrated into a clearly visible location",
                        "face not dominant in the frame",
                        "no headshot, no shoulder-up crop, no centered beauty portrait, no empty bokeh background",
                    ])
            elif generation_mode == "image":
                hard_guards.append(
                    "preserve recognizable source identity and avoid any unrequested close-up, face zoom, or portrait crop"
                )
            elif generation_mode == "mask":
                hard_guards.append(
                    "local photorealistic inpainting only inside the mask with protected regions and composition unchanged"
                )

            # 即使副模型把寫真或防肖像規則壓縮掉，送 AI Horde 前仍會固定補回。
            organized = organized + ", " + ", ".join(hard_guards)
            result["text"] = organized + (
                f" ### {negative.strip()}" if separator and negative.strip() else ""
            )

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

