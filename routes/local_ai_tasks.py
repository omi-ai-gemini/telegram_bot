import os
import secrets

from flask import Blueprint, jsonify, request

from services.local_ai_tasks import (
    claim_next_local_ai_task,
    complete_local_ai_task,
    decode_result_bytes,
    fail_local_ai_task,
    heartbeat_local_ai_task,
)


local_ai_tasks_bp = Blueprint("local_ai_tasks", __name__)


def _secret() -> str:
    return str(os.getenv("LOCAL_AI_GATEWAY_SECRET", "")).strip()


def _verify_worker():
    expected = _secret()
    if not expected:
        return False, "Render 未設定 LOCAL_AI_GATEWAY_SECRET"
    authorization = str(request.headers.get("Authorization") or "").strip()
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return False, "缺少或錯誤的 Bearer 驗證標頭"
    if not secrets.compare_digest(token.strip(), expected):
        return False, "Bearer Token 驗證失敗"
    return True, ""


@local_ai_tasks_bp.before_request
def _auth_guard():
    ok, message = _verify_worker()
    if not ok:
        return jsonify({"ok": False, "message": message}), 401
    return None


@local_ai_tasks_bp.get("/local-ai/tasks/next")
def local_ai_next_task():
    worker_id = str(request.args.get("worker_id") or "local-worker").strip()
    task = claim_next_local_ai_task(worker_id)
    if not task:
        return jsonify({"ok": True, "task": None})
    return jsonify({"ok": True, "task": task})


@local_ai_tasks_bp.post("/local-ai/tasks/<int:task_id>/heartbeat")
def local_ai_task_heartbeat(task_id: int):
    worker_id = str((request.get_json(silent=True) or {}).get("worker_id") or "").strip()
    result = heartbeat_local_ai_task(task_id, worker_id=worker_id)
    return jsonify(result)


@local_ai_tasks_bp.post("/local-ai/tasks/<int:task_id>/result")
def local_ai_task_result(task_id: int):
    payload = request.get_json(silent=True) or {}
    image_base64 = str(payload.get("image_base64") or payload.get("result_base64") or "")
    mime_type = str(payload.get("mime_type") or "image/png").strip() or "image/png"
    if not image_base64:
        return jsonify({"ok": False, "message": "缺少 result_base64"}), 400
    try:
        image_bytes = decode_result_bytes(image_base64)
    except Exception:
        return jsonify({"ok": False, "message": "result_base64 解析失敗"}), 400
    if not image_bytes:
        return jsonify({"ok": False, "message": "圖片結果為空"}), 400
    complete_local_ai_task(task_id, image_bytes, mime_type)
    return jsonify({"ok": True})


@local_ai_tasks_bp.post("/local-ai/tasks/<int:task_id>/fail")
def local_ai_task_fail(task_id: int):
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "本機 worker 執行失敗")
    canceled = bool(payload.get("canceled"))
    fail_local_ai_task(task_id, message, canceled=canceled)
    return jsonify({"ok": True})
