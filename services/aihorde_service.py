import base64
import os
from typing import Any, Dict, List, Optional, Tuple

import requests


AI_HORDE_BASE_URL = os.getenv("AI_HORDE_BASE_URL", "https://aihorde.net/api/v2").rstrip("/")
AI_HORDE_MODEL = os.getenv("AI_HORDE_MODEL", "Flux.1-Schnell fp8 (Compact)")
AI_HORDE_CLIENT_AGENT = os.getenv("AI_HORDE_CLIENT_AGENT", "TeleminiAI:1.0:telegram-image-generation")
_SESSION = requests.Session()

# 圖生圖固定使用中等重繪強度：
# - 比舊版 0.72 更能保留原圖人物、構圖與背景。
# - 仍保留足夠幅度修改提示詞明確要求的衣物、物品或場景。
IMG2IMG_DENOISING_STRENGTH = 0.50


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _keys() -> List[Tuple[int, str]]:
    values = []
    for slot in (1, 2):
        key = str(os.getenv(f"AI_HORDE_API_KEY_{slot}") or "").strip()
        if key:
            values.append((slot, key))
    return values


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "apikey": api_key,
        "Client-Agent": AI_HORDE_CLIENT_AGENT,
        "Content-Type": "application/json",
    }


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


def submit_image_request(
    job_id: int,
    prompt: str,
    source_image_bytes: bytes = b"",
    source_mime_type: str = "image/png",
    width: int = 896,
    height: int = 1152,
) -> Dict[str, Any]:
    keys = _keys()
    if not keys:
        return {"ok": False, "message": "尚未設定 AI_HORDE_API_KEY_1 / AI_HORDE_API_KEY_2"}

    preferred_index = (int(job_id) - 1) % len(keys)
    ordered = keys[preferred_index:] + keys[:preferred_index]

    width = int(width)
    height = int(height)
    steps = int(os.getenv("AI_HORDE_IMAGE_STEPS", "4"))
    allow_nsfw = _bool_env("AI_HORDE_ALLOW_NSFW", False)

    payload = {
        "prompt": str(prompt or ""),
        "params": {
            "sampler_name": "k_euler",
            "cfg_scale": 1,
            "steps": steps,
            "width": width,
            "height": height,
            "n": 1,
        },
        "models": [AI_HORDE_MODEL],
        "nsfw": allow_nsfw,
        "censor_nsfw": not allow_nsfw,
        "trusted_workers": False,
        "slow_workers": True,
        "extra_slow_workers": True,
        "r2": True,
        "shared": False,
        "replacement_filter": False,
    }

    mode = "txt2img"
    if source_image_bytes:
        mode = "img2img"
        payload["source_image"] = base64.b64encode(source_image_bytes).decode("ascii")
        payload["source_processing"] = "img2img"
        payload["params"]["denoising_strength"] = IMG2IMG_DENOISING_STRENGTH

    print(
        "AI HORDE SUBMIT PREPARED "
        f"job_id={job_id} mode={mode} model={AI_HORDE_MODEL!r} "
        f"size={width}x{height} steps={steps} "
        f"denoise={payload['params'].get('denoising_strength')}",
        flush=True,
    )

    last_error = "AI Horde 送出失敗"
    for index, (slot, key) in enumerate(ordered):
        try:
            res = _SESSION.post(
                f"{AI_HORDE_BASE_URL}/generate/async",
                headers=_headers(key),
                json=payload,
                timeout=45,
            )
        except Exception as exc:
            last_error = f"AI Horde 連線失敗：{exc}"
            if index + 1 < len(ordered):
                continue
            return {"ok": False, "message": last_error}

        data = _json_or_error(res)
        if res.ok and data.get("id"):
            return {
                "ok": True,
                "request_id": str(data.get("id")),
                "api_slot": slot,
                "kudos": data.get("kudos"),
                "warnings": data.get("warnings") or [],
            }

        last_error = _error_message(data, res.status_code)
        retryable_key_error = res.status_code in {401, 403, 429, 500, 502, 503, 504}
        if not retryable_key_error or index + 1 >= len(ordered):
            return {"ok": False, "message": last_error, "status_code": res.status_code}

    return {"ok": False, "message": last_error}


def check_image_request(request_id: str, api_slot: Optional[int] = None) -> Dict[str, Any]:
    key = dict(_keys()).get(int(api_slot or 0))
    headers = _headers(key) if key else {"Client-Agent": AI_HORDE_CLIENT_AGENT}
    try:
        res = _SESSION.get(f"{AI_HORDE_BASE_URL}/generate/check/{request_id}", headers=headers, timeout=30)
        data = _json_or_error(res)
        if not res.ok:
            return {"ok": False, "message": _error_message(data, res.status_code), "status_code": res.status_code}
        data["ok"] = True
        return data
    except Exception as exc:
        return {"ok": False, "message": f"查詢生圖狀態失敗：{exc}"}


def get_image_result(request_id: str, api_slot: Optional[int] = None) -> Dict[str, Any]:
    key = dict(_keys()).get(int(api_slot or 0))
    headers = _headers(key) if key else {"Client-Agent": AI_HORDE_CLIENT_AGENT}
    try:
        res = _SESSION.get(f"{AI_HORDE_BASE_URL}/generate/status/{request_id}", headers=headers, timeout=45)
        data = _json_or_error(res)
        if not res.ok:
            return {"ok": False, "message": _error_message(data, res.status_code), "status_code": res.status_code}
        data["ok"] = True
        return data
    except Exception as exc:
        return {"ok": False, "message": f"取得生圖結果失敗：{exc}"}


def cancel_image_request(request_id: str, api_slot: Optional[int] = None) -> bool:
    key = dict(_keys()).get(int(api_slot or 0))
    headers = _headers(key) if key else {"Client-Agent": AI_HORDE_CLIENT_AGENT}
    try:
        res = _SESSION.delete(f"{AI_HORDE_BASE_URL}/generate/status/{request_id}", headers=headers, timeout=30)
        return bool(res.ok)
    except Exception as exc:
        print("AI HORDE CANCEL ERROR:", exc, flush=True)
        return False


def download_generated_image(value: Any) -> Optional[Dict[str, Any]]:
    text = str(value or "").strip()
    if not text:
        return None

    if text.startswith("data:image/") and "," in text:
        header, encoded = text.split(",", 1)
        mime = header.split(";", 1)[0].replace("data:", "") or "image/png"
        try:
            return {"bytes": base64.b64decode(encoded), "mime_type": mime}
        except Exception:
            return None

    if text.startswith("http://") or text.startswith("https://"):
        try:
            res = _SESSION.get(text, timeout=120)
            if not res.ok:
                return None
            return {
                "bytes": res.content,
                "mime_type": (res.headers.get("content-type") or "image/png").split(";", 1)[0],
            }
        except Exception as exc:
            print("AI HORDE IMAGE DOWNLOAD ERROR:", exc, flush=True)
            return None

    try:
        return {"bytes": base64.b64decode(text), "mime_type": "image/png"}
    except Exception:
        return None
