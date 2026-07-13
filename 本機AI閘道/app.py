import hashlib
import json
import hmac
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict
from urllib.parse import urlencode

import requests
from flask import Flask, Response, jsonify, request


def _load_gateway_config() -> None:
    """Load local UTF-8 JSON config before reading environment variables.

    This avoids Windows cmd.exe code-page problems with Chinese paths.
    Environment variables still take priority over values in the JSON file.
    """
    config_path = Path(__file__).resolve().with_name("gateway_config.json")
    if not config_path.is_file():
        return

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"gateway_config.json 讀取失敗：{exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit("gateway_config.json 格式錯誤：最外層必須是 JSON 物件")

    allowed = {
        "LOCAL_AI_GATEWAY_SECRET",
        "LOCAL_AI_GATEWAY_PORT",
        "LOCAL_AI_GATEWAY_MAX_SKEW",
        "OLLAMA_BASE_URL",
        "COMFYUI_BASE_URL",
        "COMFYUI_ROOT",
        "COMFYUI_TEMP_DIR",
        "COMFYUI_TEMP_RETENTION_SECONDS",
    }
    for key in allowed:
        value = payload.get(key)
        if value is None:
            continue
        os.environ.setdefault(key, str(value))


_load_gateway_config()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

OLLAMA_BASE_URL = str(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
COMFYUI_BASE_URL = str(os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")).rstrip("/")
GATEWAY_SECRET = str(os.getenv("LOCAL_AI_GATEWAY_SECRET", "")).strip()
GATEWAY_PORT = int(os.getenv("LOCAL_AI_GATEWAY_PORT", "8787") or "8787")
MAX_CLOCK_SKEW_SECONDS = max(30, int(os.getenv("LOCAL_AI_GATEWAY_MAX_SKEW", "90") or "90"))
COMFYUI_TEMP_DIR = str(os.getenv("COMFYUI_TEMP_DIR", "")).strip()
COMFYUI_ROOT = str(os.getenv("COMFYUI_ROOT", "")).strip()
COMFYUI_TEMP_RETENTION_SECONDS = max(300, int(os.getenv("COMFYUI_TEMP_RETENTION_SECONDS", "1800") or "1800"))

_SESSION = requests.Session()
_NONCES: Dict[str, float] = {}
_NONCE_LOCK = threading.Lock()
_PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def _cleanup_nonces(now: float) -> None:
    cutoff = now - max(300, MAX_CLOCK_SKEW_SECONDS * 3)
    with _NONCE_LOCK:
        stale = [nonce for nonce, created in _NONCES.items() if created < cutoff]
        for nonce in stale:
            _NONCES.pop(nonce, None)


def _request_path_with_query() -> str:
    path = request.path
    raw_query = request.query_string.decode("utf-8", errors="strict")
    return f"{path}?{raw_query}" if raw_query else path


def _verify_request():
    if not GATEWAY_SECRET:
        return False, "本機閘道未設定 LOCAL_AI_GATEWAY_SECRET"

    timestamp = str(request.headers.get("X-Telemini-Timestamp") or "").strip()
    nonce = str(request.headers.get("X-Telemini-Nonce") or "").strip()
    signature = str(request.headers.get("X-Telemini-Signature") or "").strip().lower()

    if not timestamp or not nonce or not signature:
        return False, "缺少閘道驗證標頭"

    try:
        timestamp_value = int(timestamp)
    except Exception:
        return False, "時間戳格式錯誤"

    now = time.time()
    if abs(now - timestamp_value) > MAX_CLOCK_SKEW_SECONDS:
        return False, "請求已過期"

    _cleanup_nonces(now)
    with _NONCE_LOCK:
        if nonce in _NONCES:
            return False, "重複請求已拒絕"

    body = request.get_data(cache=True) or b""
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([
        request.method.upper(),
        _request_path_with_query(),
        timestamp,
        nonce,
        body_hash,
    ]).encode("utf-8")
    expected = hmac.new(
        GATEWAY_SECRET.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False, "簽章驗證失敗"

    with _NONCE_LOCK:
        _NONCES[nonce] = now
    return True, ""


@app.before_request
def _auth_guard():
    if request.path == "/":
        return "Not Found", 404
    ok, message = _verify_request()
    if not ok:
        return jsonify({"ok": False, "message": message}), 401
    return None


def _proxy_json(method: str, url: str, timeout: int):
    try:
        response = _SESSION.request(
            method,
            url,
            data=request.get_data(cache=True) or None,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
    except Exception as exc:
        return jsonify({"ok": False, "message": f"本機模型連線失敗：{exc}"}), 502

    content_type = response.headers.get("Content-Type") or "application/json"
    return Response(response.content, status=response.status_code, content_type=content_type)


@app.post("/v1/ollama/generate")
def ollama_generate():
    return _proxy_json("POST", f"{OLLAMA_BASE_URL}/api/generate", timeout=300)


@app.post("/v1/comfy/prompt")
def comfy_prompt():
    return _proxy_json("POST", f"{COMFYUI_BASE_URL}/prompt", timeout=60)


@app.post("/v1/comfy/interrupt")
def comfy_interrupt():
    try:
        response = _SESSION.post(f"{COMFYUI_BASE_URL}/interrupt", timeout=15)
    except Exception as exc:
        return jsonify({"ok": False, "message": f"ComfyUI interrupt 失敗：{exc}"}), 502
    return Response(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("Content-Type") or "application/json",
    )


@app.get("/v1/comfy/history/<prompt_id>")
def comfy_history(prompt_id):
    if not _PROMPT_ID_RE.fullmatch(str(prompt_id or "")):
        return jsonify({"ok": False, "message": "prompt_id 格式錯誤"}), 400
    try:
        response = _SESSION.get(f"{COMFYUI_BASE_URL}/history/{prompt_id}", timeout=30)
    except Exception as exc:
        return jsonify({"ok": False, "message": f"ComfyUI history 失敗：{exc}"}), 502
    return Response(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("Content-Type") or "application/json",
    )


def _temp_root() -> Path:
    if COMFYUI_TEMP_DIR:
        return Path(COMFYUI_TEMP_DIR).resolve()
    if COMFYUI_ROOT:
        return (Path(COMFYUI_ROOT) / "temp").resolve()
    raise RuntimeError("未設定 COMFYUI_TEMP_DIR 或 COMFYUI_ROOT")


def _cleanup_stale_temp_files() -> int:
    try:
        root = _temp_root()
    except Exception:
        return 0
    if not root.exists() or not root.is_dir():
        return 0

    cutoff = time.time() - COMFYUI_TEMP_RETENTION_SECONDS
    deleted = 0
    for candidate in root.rglob("*"):
        try:
            if not candidate.is_file():
                continue
            if candidate.stat().st_mtime >= cutoff:
                continue
            candidate.resolve().relative_to(root)
            candidate.unlink()
            deleted += 1
        except Exception:
            continue
    return deleted


def _stale_cleanup_loop() -> None:
    while True:
        deleted = _cleanup_stale_temp_files()
        if deleted:
            print(f"COMFY STALE TEMP CLEANED count={deleted}", flush=True)
        time.sleep(600)


def _clear_comfy_history_on_start() -> None:
    try:
        response = _SESSION.post(
            f"{COMFYUI_BASE_URL}/history",
            json={"clear": True},
            timeout=15,
        )
        if not response.ok:
            print("COMFY HISTORY STARTUP CLEAR FAILED", flush=True)
    except Exception:
        print("COMFY HISTORY STARTUP CLEAR FAILED", flush=True)


def _safe_temp_path(filename: str, subfolder: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError("圖片檔名格式錯誤")
    clean_subfolder = str(subfolder or "").replace("\\", "/").strip("/")
    if ".." in clean_subfolder.split("/"):
        raise ValueError("圖片子目錄格式錯誤")

    root = _temp_root()
    candidate = (root / clean_subfolder / filename).resolve()
    candidate.relative_to(root)
    return candidate


@app.get("/v1/comfy/view")
def comfy_view():
    filename = str(request.args.get("filename") or "").strip()
    subfolder = str(request.args.get("subfolder") or "").strip()
    image_type = str(request.args.get("type") or "temp").strip()
    prompt_id = str(request.args.get("prompt_id") or "").strip()

    if image_type != "temp":
        return jsonify({"ok": False, "message": "隱私模式只允許讀取 ComfyUI temp 圖片"}), 400

    if prompt_id and not _PROMPT_ID_RE.fullmatch(prompt_id):
        return jsonify({"ok": False, "message": "prompt_id 格式錯誤"}), 400

    try:
        temp_path = _safe_temp_path(filename, subfolder)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    query = urlencode({
        "filename": filename,
        "subfolder": subfolder,
        "type": image_type,
    })

    try:
        response = _SESSION.get(f"{COMFYUI_BASE_URL}/view?{query}", timeout=120)
        if not response.ok:
            return Response(
                response.content,
                status=response.status_code,
                content_type=response.headers.get("Content-Type") or "text/plain",
            )
        image_bytes = bytes(response.content)
        mime_type = response.headers.get("Content-Type") or "image/png"
    except Exception as exc:
        return jsonify({"ok": False, "message": f"ComfyUI 圖片讀取失敗：{exc}"}), 502

    delete_error = None
    for _ in range(6):
        try:
            if temp_path.is_file():
                temp_path.unlink()
            delete_error = None
            break
        except Exception as exc:
            delete_error = exc
            time.sleep(0.25)

    if delete_error is not None or temp_path.exists():
        # 不輸出路徑或檔名，避免 log 留下可追蹤資訊。
        error_type = type(delete_error).__name__ if delete_error else "FileStillExists"
        print(f"COMFY TEMP DELETE FAILED type={error_type}", flush=True)
        return jsonify({"ok": False, "message": "圖片已讀取，但 ComfyUI 暫存刪除失敗"}), 500

    if prompt_id:
        history_deleted = False
        for _ in range(3):
            try:
                history_response = _SESSION.post(
                    f"{COMFYUI_BASE_URL}/history",
                    json={"delete": [prompt_id]},
                    timeout=15,
                )
                if history_response.ok:
                    history_deleted = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not history_deleted:
            print("COMFY HISTORY DELETE FAILED", flush=True)
            return jsonify({"ok": False, "message": "圖片暫存已刪除，但 ComfyUI history 清除失敗"}), 500

    return Response(
        image_bytes,
        status=200,
        content_type=mime_type,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.after_request
def _privacy_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


if __name__ == "__main__":
    if not GATEWAY_SECRET:
        raise SystemExit("請先設定 LOCAL_AI_GATEWAY_SECRET")
    if not COMFYUI_TEMP_DIR and not COMFYUI_ROOT:
        raise SystemExit("請先設定 COMFYUI_ROOT 或 COMFYUI_TEMP_DIR")
    _cleanup_stale_temp_files()
    _clear_comfy_history_on_start()
    threading.Thread(target=_stale_cleanup_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=GATEWAY_PORT, threaded=True, debug=False)
