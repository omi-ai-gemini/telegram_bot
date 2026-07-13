import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests


_SESSION = requests.Session()

LOCAL_AI_GATEWAY_URL = str(os.getenv("LOCAL_AI_GATEWAY_URL", "")).strip().rstrip("/")
LOCAL_AI_GATEWAY_SECRET = str(os.getenv("LOCAL_AI_GATEWAY_SECRET", "")).strip()
CF_ACCESS_CLIENT_ID = str(os.getenv("CF_ACCESS_CLIENT_ID", "")).strip()
CF_ACCESS_CLIENT_SECRET = str(os.getenv("CF_ACCESS_CLIENT_SECRET", "")).strip()
LOCAL_AI_GATEWAY_TIMEOUT_SECONDS = max(
    30,
    int(os.getenv("LOCAL_AI_GATEWAY_TIMEOUT_SECONDS", "180") or "180"),
)


def gateway_requested() -> bool:
    return bool(LOCAL_AI_GATEWAY_URL or LOCAL_AI_GATEWAY_SECRET)


def gateway_enabled() -> bool:
    return bool(LOCAL_AI_GATEWAY_URL and LOCAL_AI_GATEWAY_SECRET)


def gateway_config_error() -> str:
    if not gateway_requested():
        return ""
    if not LOCAL_AI_GATEWAY_URL:
        return "已設定本機 AI 閘道密鑰，但缺少 LOCAL_AI_GATEWAY_URL"
    if not LOCAL_AI_GATEWAY_SECRET:
        return "已設定 LOCAL_AI_GATEWAY_URL，但缺少 LOCAL_AI_GATEWAY_SECRET"
    lowered = LOCAL_AI_GATEWAY_URL.lower()
    is_local = lowered.startswith("http://127.0.0.1") or lowered.startswith("http://localhost")
    if not lowered.startswith("https://") and not is_local:
        return "遠端本機 AI 閘道必須使用 HTTPS"
    return ""


def _body_bytes(payload: Optional[Dict[str, Any]]) -> bytes:
    if payload is None:
        return b""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _auth_headers(body: bytes) -> Dict[str, str]:
    """使用 HTTPS 上的 Bearer Token 驗證本機閘道。"""
    headers = {
        "Authorization": f"Bearer {LOCAL_AI_GATEWAY_SECRET}",
    }
    if body:
        headers["Content-Type"] = "application/json"
    if CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET:
        headers["CF-Access-Client-Id"] = CF_ACCESS_CLIENT_ID
        headers["CF-Access-Client-Secret"] = CF_ACCESS_CLIENT_SECRET
    return headers


def _request(
    method: str,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    config_error = gateway_config_error()
    if config_error:
        return {"ok": False, "message": config_error}
    if not gateway_enabled():
        return {"ok": False, "message": "本機 AI 閘道尚未設定"}

    query = urlencode(params or {}, doseq=True)
    path_with_query = f"{path}?{query}" if query else path
    body = _body_bytes(payload)
    headers = _auth_headers(body)
    url = f"{LOCAL_AI_GATEWAY_URL}{path_with_query}"

    try:
        response = _SESSION.request(
            method=str(method).upper(),
            url=url,
            data=body if body else None,
            headers=headers,
            timeout=timeout or LOCAL_AI_GATEWAY_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {"ok": False, "message": f"本機 AI 閘道連線失敗：{exc}"}

    if not response.ok:
        message = response.text[:500]
        try:
            payload_error = response.json()
            message = str(payload_error.get("message") or payload_error.get("error") or message)
        except Exception:
            pass
        return {
            "ok": False,
            "status_code": response.status_code,
            "message": f"本機 AI 閘道 HTTP {response.status_code}: {message}",
        }

    return {"ok": True, "response": response}


def gateway_post_json(
    path: str,
    payload: Dict[str, Any],
    *,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    result = _request("POST", path, payload=payload, timeout=timeout)
    if not result.get("ok"):
        return result
    try:
        return {"ok": True, "data": result["response"].json()}
    except Exception as exc:
        return {"ok": False, "message": f"本機 AI 閘道 JSON 解析失敗：{exc}"}


def gateway_get_json(
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    result = _request("GET", path, params=params, timeout=timeout)
    if not result.get("ok"):
        return result
    try:
        return {"ok": True, "data": result["response"].json()}
    except Exception as exc:
        return {"ok": False, "message": f"本機 AI 閘道 JSON 解析失敗：{exc}"}


def gateway_get_bytes(
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    result = _request("GET", path, params=params, timeout=timeout)
    if not result.get("ok"):
        return result
    response = result["response"]
    return {
        "ok": True,
        "bytes": response.content,
        "mime_type": response.headers.get("Content-Type") or "application/octet-stream",
    }
