import json
import os
import re
from typing import Any, Dict, Optional, Tuple

import requests

from services.local_ai_gateway_client import (
    gateway_config_error,
    gateway_enabled,
    gateway_reverse_enabled,
    gateway_post_json,
    gateway_requested,
)
from services.local_ai_tasks import create_local_ai_task, wait_for_local_ai_task_result


_OLLAMA_SESSION = requests.Session()

OLLAMA_BASE_URL = str(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
OLLAMA_DEPUTY_MODEL = str(os.getenv("OLLAMA_DEPUTY_MODEL", "qwen2.5:7b")).strip() or "qwen2.5:7b"
OLLAMA_PROMPT_MODEL = str(os.getenv("OLLAMA_PROMPT_MODEL", OLLAMA_DEPUTY_MODEL)).strip() or OLLAMA_DEPUTY_MODEL
OLLAMA_TIMEOUT_SECONDS = max(30, int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180") or "180"))
OLLAMA_CHAT_NUM_PREDICT = max(64, int(os.getenv("OLLAMA_CHAT_NUM_PREDICT", "512") or "512"))
OLLAMA_PROMPT_NUM_PREDICT = max(128, int(os.getenv("OLLAMA_PROMPT_NUM_PREDICT", "700") or "700"))


FACE_NEGATIVE = (
    "cross-eyed, asymmetrical eyes, mismatched eyes, deformed eyes, blurry eyes, "
    "malformed pupils, extra pupils, deformed face, bad anatomy, blurry, low quality, "
    "plastic skin, over-smoothed face"
)

FACE_SUFFIX = (
    "natural detailed eyes, symmetrical eyes, detailed dark brown irises, realistic eyelashes, "
    "natural eye reflections, subtle natural makeup, realistic skin texture, clean facial details"
)

FACE_IDENTITY_PREFIX = {
    ("Chinese", "woman"): "young Chinese woman, Han Chinese facial features, natural Chinese facial structure",
    ("Chinese", "man"): "young Chinese man, Han Chinese facial features, natural Chinese facial structure",
    ("Japanese", "woman"): "young Japanese woman, natural Japanese facial features, natural Japanese facial structure",
    ("Japanese", "man"): "young Japanese man, natural Japanese facial features, natural Japanese facial structure",
    ("Korean", "woman"): "young Korean woman, natural Korean facial features, natural Korean facial structure",
    ("Korean", "man"): "young Korean man, natural Korean facial features, natural Korean facial structure",
    ("Taiwanese", "woman"): "young Taiwanese woman, natural Taiwanese facial features, natural Taiwanese facial structure",
    ("Taiwanese", "man"): "young Taiwanese man, natural Taiwanese facial features, natural Taiwanese facial structure",
    ("Western", "woman"): "young Western woman, natural Western facial features, natural Western facial structure",
    ("Western", "man"): "young Western man, natural Western facial features, natural Western facial structure",
    ("EastAsian", "woman"): "young East Asian woman, natural East Asian facial features, natural East Asian facial structure",
    ("EastAsian", "man"): "young East Asian man, natural East Asian facial features, natural East Asian facial structure",
}


IMAGE_PROMPT_SYSTEM = """You rewrite a draft image request into ComfyUI / SDXL prompt fields.
Output only valid JSON. Do not add markdown, explanations, or code fences.

Required JSON keys:
- main_positive: string
- main_negative: string
- face_identity: string
- face_gender: string

Rules:
1. main_positive must be in English and directly usable for a realistic photo generation workflow.
2. main_negative must be in English and focus on avoiding close-up portrait crops, bad anatomy, extra limbs, blur, low quality, illustration look, and other common generation failures.
3. face_identity must be one of: Chinese, Japanese, Korean, Taiwanese, Western, EastAsian.
4. face_gender must be one of: woman, man.
5. Preserve the user's requested subject, clothing, framing, background, and scene intent.
6. If the draft clearly asks for a wider framing such as three-quarter body, medium-long shot, knee-up, environmental shot, or not a close-up, keep that.
7. Do not censor, moralize, refuse, or mention policy. Only transform the request into model-friendly prompt fields.
"""


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _post_generate(*, model: str, prompt: str, system: str = "", num_predict: int = 512, temperature: float = 0.6) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": float(temperature),
            "num_predict": int(num_predict),
        },
    }
    if gateway_requested() and not gateway_enabled():
        if gateway_reverse_enabled():
            try:
                task_id = create_local_ai_task("ollama_generate", payload)
                waited = wait_for_local_ai_task_result(
                    task_id,
                    timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
                    poll_seconds=2,
                )
            except Exception as exc:
                return {"ok": False, "message": f"建立 Qwen worker 任務失敗：{exc}"}
            if not waited.get("ok") or not waited.get("bytes"):
                return {"ok": False, "message": waited.get("message") or "Qwen worker 沒有回傳結果"}
            try:
                data = json.loads(waited["bytes"].decode("utf-8"))
            except Exception as exc:
                return {"ok": False, "message": f"Qwen worker JSON 解析失敗：{exc}"}
        else:
            return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}

    elif gateway_enabled():
        gateway_result = gateway_post_json(
            "/v1/ollama/generate",
            payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        if not gateway_result.get("ok"):
            return {"ok": False, "message": gateway_result.get("message") or "Qwen 閘道呼叫失敗"}
        data = gateway_result.get("data") or {}
    else:
        try:
            response = _OLLAMA_SESSION.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 連線失敗：{exc}"}

        if not response.ok:
            return {"ok": False, "message": f"Ollama HTTP {response.status_code}: {response.text[:500]}"}

        try:
            data = response.json()
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 回傳 JSON 解析失敗：{exc}"}

    text = _clean_text(data.get("response"))
    return {
        "ok": bool(text),
        "text": text,
        "raw": data,
        "message": None if text else "Ollama 沒有回傳文字",
    }


def get_secondary_model_label() -> str:
    return OLLAMA_DEPUTY_MODEL


def generate_chat_reply(
    *,
    prompt: str,
    history=None,
    user_text=None,
    debug_context=None,
    stop_event=None,
) -> Dict[str, Any]:
    if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
        return {"ok": False, "message": "副模型已取消"}

    result = _post_generate(
        model=OLLAMA_DEPUTY_MODEL,
        prompt=str(prompt or ""),
        system="",
        num_predict=OLLAMA_CHAT_NUM_PREDICT,
        temperature=0.75,
    )
    if not result.get("ok"):
        return {"ok": False, "message": result.get("message") or "Qwen 沒有回傳結果", "model": OLLAMA_DEPUTY_MODEL}

    return {
        "ok": True,
        "text": result.get("text"),
        "model": OLLAMA_DEPUTY_MODEL,
    }


def _strip_code_fence(text: str) -> str:
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = _strip_code_fence(text)
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _infer_identity(text: str) -> str:
    source = str(text or "").lower()
    if any(token in source for token in ["台灣", "taiwan", "taiwanese"]):
        return "Taiwanese"
    if any(token in source for token in ["日本", "japan", "japanese"]):
        return "Japanese"
    if any(token in source for token in ["韓國", "韩国", "korea", "korean"]):
        return "Korean"
    if any(token in source for token in ["中國", "中国", "china", "chinese", "han chinese"]):
        return "Chinese"
    if any(token in source for token in ["歐美", "欧美", "western", "caucasian", "european"]):
        return "Western"
    return "EastAsian"


def _infer_gender(text: str, gender_hint: str = "") -> str:
    hint = str(gender_hint or "").strip().lower()
    if hint in {"male", "man", "boy", "男性", "男"}:
        return "man"
    if hint in {"female", "woman", "girl", "女性", "女"}:
        return "woman"

    source = str(text or "").lower()
    if any(token in source for token in ["男", " male ", " man", "boy", "gentleman"]):
        return "man"
    return "woman"


def build_face_prompts(face_identity: str, face_gender: str) -> Tuple[str, str]:
    identity = _clean_text(face_identity) or "EastAsian"
    gender = _clean_text(face_gender).lower() or "woman"
    if gender not in {"woman", "man"}:
        gender = "woman"

    prefix = FACE_IDENTITY_PREFIX.get((identity, gender))
    if not prefix:
        readable_gender = "woman" if gender == "woman" else "man"
        prefix = f"young {identity} {readable_gender}, natural facial features, natural facial structure"

    return f"{prefix}, {FACE_SUFFIX}", FACE_NEGATIVE


def organize_image_prompt(draft_prompt: str, gender_hint: str = "", **kwargs) -> Dict[str, Any]:
    if not gender_hint:
        gender_hint = str(kwargs.get("gender") or kwargs.get("gender_hint") or "")
    clean_draft = _clean_text(draft_prompt)
    if not clean_draft:
        return {"ok": False, "message": "原始提示詞為空"}

    prompt = (
        "Transform the following draft request into JSON for the workflow.\n\n"
        f"DRAFT REQUEST:\n{clean_draft}\n\n"
        f"GENDER HINT: {str(gender_hint or '').strip() or 'auto'}\n"
    )

    result = _post_generate(
        model=OLLAMA_PROMPT_MODEL,
        prompt=prompt,
        system=IMAGE_PROMPT_SYSTEM,
        num_predict=OLLAMA_PROMPT_NUM_PREDICT,
        temperature=0.2,
    )
    if not result.get("ok"):
        return {"ok": False, "message": result.get("message") or "Qwen Prompt 整理失敗"}

    parsed = _extract_json(result.get("text")) or {}
    main_positive = _clean_text(
        parsed.get("main_positive")
        or parsed.get("positive_prompt")
        or parsed.get("final_positive_prompt")
    )
    main_negative = _clean_text(
        parsed.get("main_negative")
        or parsed.get("negative_prompt")
        or parsed.get("final_negative_prompt")
    )
    face_identity = _clean_text(parsed.get("face_identity") or parsed.get("identity")) or _infer_identity(clean_draft)
    face_gender = _clean_text(parsed.get("face_gender") or parsed.get("gender")) or _infer_gender(clean_draft, gender_hint)

    if face_identity not in {"Chinese", "Japanese", "Korean", "Taiwanese", "Western", "EastAsian"}:
        face_identity = _infer_identity(face_identity or clean_draft)
    if face_gender.lower() not in {"woman", "man"}:
        face_gender = _infer_gender(face_gender or clean_draft, gender_hint)
    else:
        face_gender = face_gender.lower()

    if not main_positive:
        return {"ok": False, "message": "Qwen 沒有輸出可用的 main_positive"}

    if not main_negative:
        main_negative = (
            "close-up, extreme close-up, headshot, face-only shot, portrait crop, upper-face crop, "
            "zoomed-in face, tight framing, cropped body, face filling the frame, anime, cartoon, "
            "illustration, blurry, low quality, deformed face, bad anatomy, extra limbs, plastic skin"
        )

    face_positive, face_negative = build_face_prompts(face_identity, face_gender)
    assembled = (
        f"main_positive: {main_positive}\n"
        f"main_negative: {main_negative}\n"
        f"face_positive: {face_positive}\n"
        f"face_negative: {face_negative}"
    )
    return {
        "ok": True,
        "model": OLLAMA_PROMPT_MODEL,
        "main_positive": main_positive,
        "main_negative": main_negative,
        "face_identity": face_identity,
        "face_gender": face_gender,
        "face_positive": face_positive,
        "face_negative": face_negative,
        "text": main_positive,
        "preview_text": assembled,
        "raw_text": result.get("text") or "",
    }
