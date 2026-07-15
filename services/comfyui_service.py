import os
import random
import time
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

import requests

from services.local_ai_gateway_client import (
    gateway_config_error,
    gateway_enabled,
    gateway_reverse_enabled,
    gateway_requested,
    gateway_get_bytes,
    gateway_get_json,
    gateway_post_json,
)
from services.local_ai_tasks import (
    cancel_local_ai_task,
    create_local_ai_task,
    wait_for_local_ai_task_result,
)


_COMFY_SESSION = requests.Session()

COMFYUI_BASE_URL = str(os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")).rstrip("/")
COMFYUI_TIMEOUT_SECONDS = max(60, int(os.getenv("COMFYUI_TIMEOUT_SECONDS", "900") or "900"))
COMFYUI_POLL_SECONDS = max(1, int(os.getenv("COMFYUI_POLL_SECONDS", "2") or "2"))
COMFYUI_CHECKPOINT = str(os.getenv("COMFYUI_CHECKPOINT", "cyberrealisticXL_v100.safetensors")).strip() or "cyberrealisticXL_v100.safetensors"
COMFYUI_UPSCALE_MODEL = str(os.getenv("COMFYUI_UPSCALE_MODEL", "RealESRGAN_x2plus.pth")).strip() or "RealESRGAN_x2plus.pth"
COMFYUI_FACE_DETECTOR = str(os.getenv("COMFYUI_FACE_DETECTOR", "bbox/face_yolov8m.pt")).strip() or "bbox/face_yolov8m.pt"
COMFYUI_WIDTH = max(256, int(os.getenv("COMFYUI_WIDTH", "768") or "768"))
COMFYUI_HEIGHT = max(256, int(os.getenv("COMFYUI_HEIGHT", "1024") or "1024"))
COMFYUI_TEMP_DIR = str(os.getenv("COMFYUI_TEMP_DIR", "")).strip()
COMFYUI_ROOT = str(os.getenv("COMFYUI_ROOT", "")).strip()
_LOCAL_TASK_PREFIX = "localtask:"


def _workflow_seed() -> int:
    return random.SystemRandom().randint(1, 2**62)


def build_txt2img_workflow(
    *,
    main_positive: str,
    main_negative: str,
    face_positive: str,
    face_negative: str,
) -> Dict[str, Any]:
    return {
        "10": {
            "inputs": {"text": str(main_negative or ""), "clip": ["12", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP 文字編碼（負面提示詞）"},
        },
        "11": {
            "inputs": {"text": str(main_positive or ""), "clip": ["12", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP 文字編碼（正面提示詞）"},
        },
        "12": {
            "inputs": {"ckpt_name": COMFYUI_CHECKPOINT},
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "載入檢查點"},
        },
        "13": {
            "inputs": {
                "seed": _workflow_seed(),
                "steps": 25,
                "cfg": 5.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1,
                "model": ["12", 0],
                "positive": ["11", 0],
                "negative": ["10", 0],
                "latent_image": ["14", 0],
            },
            "class_type": "KSampler",
            "_meta": {"title": "KSampler"},
        },
        "14": {
            "inputs": {"width": COMFYUI_WIDTH, "height": COMFYUI_HEIGHT, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "空白潛在影像"},
        },
        "16": {
            "inputs": {"samples": ["13", 0], "vae": ["12", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "VAE 解碼"},
        },
        "17": {
            "inputs": {"model_name": COMFYUI_UPSCALE_MODEL},
            "class_type": "UpscaleModelLoader",
            "_meta": {"title": "載入放大模型"},
        },
        "18": {
            "inputs": {"upscale_model": ["17", 0], "image": ["19", 0]},
            "class_type": "ImageUpscaleWithModel",
            "_meta": {"title": "圖片放大（使用模型）"},
        },
        "19": {
            "inputs": {
                "guide_size": 512,
                "guide_size_for": True,
                "max_size": 1024,
                "seed": _workflow_seed(),
                "steps": 20,
                "cfg": 5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 0.25,
                "feather": 5,
                "noise_mask": True,
                "force_inpaint": True,
                "bbox_threshold": 0.5,
                "bbox_dilation": 10,
                "bbox_crop_factor": 3,
                "sam_detection_hint": "center-1",
                "sam_dilation": 0,
                "sam_threshold": 0.93,
                "sam_bbox_expansion": 0,
                "sam_mask_hint_threshold": 0.7,
                "sam_mask_hint_use_negative": "False",
                "drop_size": 10,
                "wildcard": "",
                "cycle": 1,
                "inpaint_model": False,
                "noise_mask_feather": 20,
                "tiled_encode": False,
                "tiled_decode": False,
                "image": ["16", 0],
                "model": ["12", 0],
                "clip": ["12", 1],
                "vae": ["12", 2],
                "positive": ["23", 0],
                "negative": ["24", 0],
                "bbox_detector": ["20", 0],
            },
            "class_type": "FaceDetailer",
            "_meta": {"title": "FaceDetailer"},
        },
        "20": {
            "inputs": {"model_name": COMFYUI_FACE_DETECTOR},
            "class_type": "UltralyticsDetectorProvider",
            "_meta": {"title": "UltralyticsDetectorProvider"},
        },
        "23": {
            "inputs": {"text": str(face_positive or ""), "clip": ["12", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP 文字編碼（Face 正面）"},
        },
        "24": {
            "inputs": {"text": str(face_negative or ""), "clip": ["12", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP 文字編碼（Face 負面）"},
        },
        "25": {
            "inputs": {"images": ["18", 0]},
            "class_type": "PreviewImage",
            "_meta": {"title": "預覽圖片"},
        },
    }


def _post_json(path: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    if gateway_reverse_enabled():
        if path != "/prompt":
            return {"ok": False, "message": f"反向 worker 模式不支援直接呼叫：{path}"}
        try:
            task_id = create_local_ai_task("comfy_txt2img", payload)
        except Exception as exc:
            return {"ok": False, "message": f"建立本機 worker 任務失敗：{exc}"}
        return {
            "ok": True,
            "data": {
                "prompt_id": f"{_LOCAL_TASK_PREFIX}{task_id}",
                "task_id": task_id,
                "mode": "local_worker",
            },
        }

    if gateway_requested() and not gateway_enabled():
        return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}
    if gateway_enabled():
        gateway_path = {
            "/prompt": "/v1/comfy/prompt",
            "/interrupt": "/v1/comfy/interrupt",
        }.get(path)
        if not gateway_path:
            return {"ok": False, "message": f"不支援的 ComfyUI 閘道路徑：{path}"}
        return gateway_post_json(gateway_path, payload, timeout=timeout)

    url = f"{COMFYUI_BASE_URL}{path}"
    try:
        response = _COMFY_SESSION.post(url, json=payload, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "message": f"ComfyUI 連線失敗：{exc}"}
    if not response.ok:
        return {"ok": False, "message": f"ComfyUI HTTP {response.status_code}: {response.text[:500]}"}
    try:
        data = response.json()
    except Exception as exc:
        return {"ok": False, "message": f"ComfyUI JSON 解析失敗：{exc}"}
    return {"ok": True, "data": data}


def queue_prompt(workflow: Dict[str, Any]) -> Dict[str, Any]:
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    result = _post_json("/prompt", payload, timeout=60)
    if not result.get("ok"):
        return result
    data = result.get("data") or {}
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        return {"ok": False, "message": "ComfyUI 沒有回傳 prompt_id"}
    return {"ok": True, "prompt_id": prompt_id, "client_id": client_id, "raw": data}


def interrupt() -> None:
    try:
        if gateway_enabled():
            gateway_post_json("/v1/comfy/interrupt", {}, timeout=10)
        else:
            _COMFY_SESSION.post(f"{COMFYUI_BASE_URL}/interrupt", timeout=10)
    except Exception:
        return


def _local_task_id_from_prompt(prompt_id: str) -> Optional[int]:
    text = str(prompt_id or "")
    if not text.startswith(_LOCAL_TASK_PREFIX):
        return None
    try:
        return int(text[len(_LOCAL_TASK_PREFIX):])
    except Exception:
        return None


def _get_history(prompt_id: str) -> Dict[str, Any]:
    if gateway_requested() and not gateway_enabled():
        return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}
    if gateway_enabled():
        return gateway_get_json(f"/v1/comfy/history/{prompt_id}", timeout=30)

    url = f"{COMFYUI_BASE_URL}/history/{prompt_id}"
    try:
        response = _COMFY_SESSION.get(url, timeout=30)
    except Exception as exc:
        return {"ok": False, "message": f"ComfyUI 查詢 history 失敗：{exc}"}
    if not response.ok:
        return {"ok": False, "message": f"ComfyUI history HTTP {response.status_code}: {response.text[:500]}"}
    try:
        data = response.json()
    except Exception as exc:
        return {"ok": False, "message": f"ComfyUI history JSON 解析失敗：{exc}"}
    return {"ok": True, "data": data}


def _pick_image_meta(history_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(history_payload, dict) or not history_payload:
        return None
    entry = next(iter(history_payload.values()), None)
    if not isinstance(entry, dict):
        return None
    outputs = entry.get("outputs") or {}
    preferred = ["25", "18", "19", "16"]
    for node_id in preferred:
        node_output = outputs.get(node_id) or {}
        images = node_output.get("images") or []
        if images:
            return images[0]
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        images = node_output.get("images") or []
        if images:
            return images[0]
    return None


def _safe_delete_direct_temp(image_meta: Dict[str, Any]) -> bool:
    if str(image_meta.get("type") or "temp") != "temp":
        return False
    try:
        from pathlib import Path
        if COMFYUI_TEMP_DIR:
            root = Path(COMFYUI_TEMP_DIR).resolve()
        elif COMFYUI_ROOT:
            root = (Path(COMFYUI_ROOT) / "temp").resolve()
        else:
            return False
        subfolder = str(image_meta.get("subfolder") or "").replace("\\", "/").strip("/")
        filename = Path(str(image_meta.get("filename") or "")).name
        candidate = (root / subfolder / filename).resolve()
        candidate.relative_to(root)
        for _ in range(6):
            try:
                if candidate.is_file():
                    candidate.unlink()
                return not candidate.exists()
            except Exception:
                time.sleep(0.25)
        return False
    except Exception:
        return False


def _delete_direct_history(prompt_id: str) -> bool:
    if not prompt_id:
        return True
    try:
        response = _COMFY_SESSION.post(
            f"{COMFYUI_BASE_URL}/history",
            json={"delete": [str(prompt_id)]},
            timeout=15,
        )
        return bool(response.ok)
    except Exception:
        return False


def _download_view(image_meta: Dict[str, Any], prompt_id: str = "") -> Dict[str, Any]:
    if gateway_requested() and not gateway_enabled():
        return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}
    params = {
        "filename": image_meta.get("filename", ""),
        "subfolder": image_meta.get("subfolder", ""),
        "type": image_meta.get("type", "temp"),
    }
    if gateway_enabled():
        gateway_params = dict(params)
        gateway_params["prompt_id"] = str(prompt_id or "")
        return gateway_get_bytes("/v1/comfy/view", params=gateway_params, timeout=120)

    query = urlencode(params)
    url = f"{COMFYUI_BASE_URL}/view?{query}"
    try:
        response = _COMFY_SESSION.get(url, timeout=120)
    except Exception as exc:
        return {"ok": False, "message": f"ComfyUI 下載圖片失敗：{exc}"}
    if not response.ok:
        return {"ok": False, "message": f"ComfyUI view HTTP {response.status_code}: {response.text[:500]}"}
    result = {
        "ok": True,
        "bytes": response.content,
        "mime_type": response.headers.get("Content-Type") or "image/png",
    }
    if not _safe_delete_direct_temp(image_meta):
        return {"ok": False, "message": "圖片已讀取，但 ComfyUI temp 暫存清除失敗；請設定 COMFYUI_ROOT"}
    if prompt_id and not _delete_direct_history(prompt_id):
        return {"ok": False, "message": "圖片已讀取，但 ComfyUI history 清除失敗"}
    return result


def wait_for_prompt_image(
    prompt_id: str,
    *,
    timeout_seconds: Optional[int] = None,
    poll_seconds: Optional[int] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    timeout_seconds = int(timeout_seconds or COMFYUI_TIMEOUT_SECONDS)
    poll_seconds = int(poll_seconds or COMFYUI_POLL_SECONDS)
    local_task_id = _local_task_id_from_prompt(prompt_id)
    if local_task_id is not None:
        return wait_for_local_ai_task_result(
            local_task_id,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    started = time.monotonic()

    while True:
        if progress_callback:
            try:
                progress_callback()
            except Exception:
                pass

        if cancel_check and cancel_check():
            local_task_id = _local_task_id_from_prompt(prompt_id)
            if local_task_id is not None:
                cancel_local_ai_task(local_task_id)
                return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}
            interrupt()
            return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}

        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            return {"ok": False, "message": f"ComfyUI 等待超過 {timeout_seconds} 秒"}

        history = _get_history(prompt_id)
        if history.get("ok"):
            image_meta = _pick_image_meta(history.get("data") or {})
            if image_meta:
                downloaded = _download_view(image_meta, prompt_id)
                if downloaded.get("ok"):
                    return downloaded
                return {"ok": False, "message": downloaded.get("message") or "ComfyUI 圖片下載失敗"}

            payload = history.get("data") or {}
            entry = next(iter(payload.values()), None)
            if isinstance(entry, dict):
                status = entry.get("status") or {}
                status_str = str(status.get("status_str") or "")
                if status_str.lower() == "error":
                    messages = status.get("messages") or []
                    return {"ok": False, "message": f"ComfyUI 執行失敗：{messages}"}

        time.sleep(max(1, poll_seconds))
