import base64
import os
from typing import Any, Dict, List, Optional, Tuple

import requests


AI_HORDE_BASE_URL = os.getenv("AI_HORDE_BASE_URL", "https://aihorde.net/api/v2").rstrip("/")
# 依模式分流模型：
# - 文生圖預設改為較適合寫真路線的 SDXL 模型。
# - 整體圖生圖與局部遮罩改用較穩定的寫實模型／inpainting 模型。
# 仍保留環境變數覆蓋能力，讓你可以隨時改回自己要的模型。
AI_HORDE_TXT2IMG_MODEL = os.getenv("AI_HORDE_TXT2IMG_MODEL", "AlbedoBase XL (SDXL)")
AI_HORDE_IMG2IMG_MODEL = os.getenv("AI_HORDE_IMG2IMG_MODEL", "Realistic Vision")
AI_HORDE_INPAINT_MODEL = os.getenv("AI_HORDE_INPAINT_MODEL", "Realistic Vision Inpainting")
AI_HORDE_CLIENT_AGENT = os.getenv("AI_HORDE_CLIENT_AGENT", "TeleminiAI:1.0:telegram-image-generation")
_SESSION = requests.Session()

# 新預設值改成較適合寫真模型的參數，不再沿用 Flux Schnell 的極低 steps。
TXT2IMG_STEPS = int(os.getenv("AI_HORDE_TXT2IMG_STEPS", "28"))
IMG2IMG_STEPS = int(os.getenv("AI_HORDE_IMG2IMG_STEPS", "28"))
INPAINT_STEPS = int(os.getenv("AI_HORDE_INPAINT_STEPS", "24"))

try:
    TXT2IMG_CFG_SCALE = float(os.getenv("AI_HORDE_TXT2IMG_CFG_SCALE", "5.5"))
except Exception:
    TXT2IMG_CFG_SCALE = 5.5

try:
    IMG2IMG_CFG_SCALE = float(os.getenv("AI_HORDE_IMG2IMG_CFG_SCALE", "5.0"))
except Exception:
    IMG2IMG_CFG_SCALE = 5.0

try:
    IMG2IMG_DENOISING_STRENGTH = float(
        os.getenv("AI_HORDE_IMG2IMG_DENOISING_STRENGTH", "0.72")
    )
except Exception:
    IMG2IMG_DENOISING_STRENGTH = 0.72
IMG2IMG_DENOISING_STRENGTH = max(0.05, min(1.0, IMG2IMG_DENOISING_STRENGTH))

try:
    INPAINT_CFG_SCALE = float(os.getenv("AI_HORDE_INPAINT_CFG_SCALE", "7"))
except Exception:
    INPAINT_CFG_SCALE = 7.0

try:
    INPAINT_DENOISING_STRENGTH = float(
        os.getenv("AI_HORDE_INPAINT_DENOISING_STRENGTH", "0.72")
    )
except Exception:
    INPAINT_DENOISING_STRENGTH = 0.72
INPAINT_DENOISING_STRENGTH = max(0.05, min(1.0, INPAINT_DENOISING_STRENGTH))


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


def _clamp(value: float, minimum: float = 0.05, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _looks_like_color_only_edit(prompt: str) -> bool:
    text = str(prompt or "").lower()
    color_words = [
        "顏色", "改色", "換色", "變成黃色", "變黃色", "黃色",
        "color", "recolor", "change the color", "yellow", "red", "blue", "green",
    ]
    restructure_words = [
        "蕾絲", "花紋", "圖案", "材質", "款式", "style", "pattern", "texture", "lace", "replace",
        "換掉", "替換", "改款", "重做", "remove", "add", "pose", "坐姿", "站姿",
    ]
    return any(word in text for word in color_words) and not any(word in text for word in restructure_words)


def _pick_denoising_strength(mode: str, prompt: str) -> float:
    text = str(prompt or "").lower()
    if mode == "inpainting":
        if _looks_like_color_only_edit(text):
            return _clamp(float(os.getenv("AI_HORDE_INPAINT_DENOISE_COLOR_ONLY", "0.32")))
        if any(word in text for word in ["蕾絲", "花紋", "圖案", "材質", "pattern", "texture", "lace"]):
            return _clamp(float(os.getenv("AI_HORDE_INPAINT_DENOISE_PATTERN", "0.50")))
        return INPAINT_DENOISING_STRENGTH

    if mode == "img2img":
        if any(word in text for word in ["坐姿", "站姿", "pose", "sitting", "standing", "跪", "蹲", "躺", "趴"]):
            return _clamp(float(os.getenv("AI_HORDE_IMG2IMG_DENOISE_POSE", "0.82")))
        if _looks_like_color_only_edit(text):
            return _clamp(float(os.getenv("AI_HORDE_IMG2IMG_DENOISE_COLOR_ONLY", "0.58")))
        return IMG2IMG_DENOISING_STRENGTH

    return 0.0


def submit_image_request(
    job_id: int,
    prompt: str,
    source_image_bytes: bytes = b"",
    source_mime_type: str = "image/png",
    source_mask_bytes: bytes = b"",
    source_mask_mime_type: str = "image/png",
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
    allow_nsfw = _bool_env("AI_HORDE_ALLOW_NSFW", True)
    has_source = bool(source_image_bytes)
    has_mask = bool(source_image_bytes and source_mask_bytes)
    mode = "inpainting" if has_mask else ("img2img" if has_source else "txt2img")

    if mode == "inpainting":
        model_name = AI_HORDE_INPAINT_MODEL
        steps = INPAINT_STEPS
        cfg_scale = INPAINT_CFG_SCALE
    elif mode == "img2img":
        model_name = AI_HORDE_IMG2IMG_MODEL
        steps = IMG2IMG_STEPS
        cfg_scale = IMG2IMG_CFG_SCALE
    else:
        model_name = AI_HORDE_TXT2IMG_MODEL
        steps = TXT2IMG_STEPS
        cfg_scale = TXT2IMG_CFG_SCALE

    payload = {
        "prompt": str(prompt or ""),
        "params": {
            "sampler_name": "k_euler",
            "cfg_scale": cfg_scale,
            "steps": steps,
            "width": width,
            "height": height,
            "n": 1,
        },
        "models": [model_name],
        "nsfw": allow_nsfw,
        "censor_nsfw": not allow_nsfw,
        "trusted_workers": False,
        "slow_workers": True,
        "extra_slow_workers": True,
        "r2": True,
        "shared": False,
        "replacement_filter": False,
    }

    if source_image_bytes:
        payload["source_image"] = base64.b64encode(source_image_bytes).decode("ascii")
        if has_mask:
            payload["source_mask"] = base64.b64encode(source_mask_bytes).decode("ascii")
            payload["source_processing"] = "inpainting"
            payload["params"]["denoising_strength"] = _pick_denoising_strength("inpainting", prompt)
        else:
            payload["source_processing"] = "img2img"
            payload["params"]["denoising_strength"] = _pick_denoising_strength("img2img", prompt)

    print(
        "AI HORDE SUBMIT PREPARED "
        f"job_id={job_id} mode={mode} model={model_name!r} "
        f"size={width}x{height} steps={steps} cfg={cfg_scale} "
        f"has_mask={has_mask} denoise={payload['params'].get('denoising_strength')}",
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
