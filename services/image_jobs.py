import os
import secrets
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.aihorde_service import (
    cancel_image_request,
    check_image_request,
    download_generated_image,
    get_image_result,
    submit_image_request,
)
from services.crypto_env import aad_for, decrypt_text, encrypt_text, is_encrypted
from services.comfyui_service import build_txt2img_workflow, queue_prompt, wait_for_prompt_image
from services.qwen_service import build_face_prompts, get_secondary_model_label, organize_image_prompt
from services.database import get_conn
from services.image_prepare import OUTPUT_HEIGHT, OUTPUT_WIDTH, prepare_img2img_source
from services.image_store import download_image_asset, save_image_asset
from services.local_ai_tasks import cancel_local_ai_task
from services.telegram_service import delete_message, edit_message_text, send_message, send_photo_bytes


ACTIVE_STATUSES = ("created", "prompting", "submitting", "queued", "processing")
MAX_ACTIVE_PER_USER = 3
QUEUE_TIMEOUT_SECONDS = 30 * 60
PURE_TEXT_LOCAL_QUEUE_TIMEOUT_SECONDS = max(
    60 * 60,
    int(os.getenv("OMI_TXT2IMG_QUEUE_TIMEOUT_SECONDS", str(24 * 60 * 60)) or str(24 * 60 * 60)),
)
POLL_SECONDS = 4
STATUS_UPDATE_SECONDS = 10
QWEN_RETRY_SECONDS = 30
BASE_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "static" / "image_reference"
BASE_REFERENCE_FILES = {
    "male": "male_reference.png",
    "female": "female_reference.png",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _extract_message_id(result):
    if not isinstance(result, dict):
        return None
    return (result.get("result") or {}).get("message_id")


def _cancel_markup(job_id: int):
    return {
        "inline_keyboard": [[
            {"text": "取消生圖", "callback_data": f"image_cancel:{int(job_id)}"}
        ]]
    }


def _delete_notice_markup(job_id: int):
    return {
        "inline_keyboard": [[
            {"text": "刪除訊息", "callback_data": f"image_notice_delete:{int(job_id)}"}
        ]]
    }


def _encrypt_prompt(job_id: int, prompt: str, field: str = "final_prompt") -> str:
    try:
        return encrypt_text(prompt, aad=aad_for("image_generation_jobs", field, job_id))
    except Exception as exc:
        print(f"IMAGE PROMPT ENCRYPT ERROR field={field}:", exc, flush=True)
        return prompt


def _decrypt_prompt(job_id: int, value: str, field: str = "final_prompt") -> str:
    if not is_encrypted(value):
        return _text(value)
    try:
        return decrypt_text(value, aad=aad_for("image_generation_jobs", field, job_id))
    except Exception as exc:
        print("IMAGE PROMPT DECRYPT ERROR:", exc, flush=True)
        return ""




def _count_active(user_id: Any) -> int:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM image_generation_jobs
            WHERE user_id=%s AND status = ANY(%s)
        """, (_text(user_id), list(ACTIVE_STATUSES)))
        row = cursor.fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def create_image_job(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    action_id: Any,
    gender: str,
    generation_mode: str,
    prompt_mode: str,
    source_choice: str,
    fixed_tag: str,
    final_prompt: str,
    reference_type: str,
    reference_code: Optional[str] = None,
    custom_upload: Optional[Dict[str, Any]] = None,
    custom_mask: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cursor = conn.cursor()

        # 同一個 user 的送出動作使用 PostgreSQL transaction advisory lock，
        # 避免連點或多 worker 同時通過檢查，確保真的最多 3 張。
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_text(user_id),))
        cursor.execute("""
            SELECT COUNT(*)
            FROM image_generation_jobs
            WHERE user_id=%s AND status = ANY(%s)
        """, (_text(user_id), list(ACTIVE_STATUSES)))
        active_count = int((cursor.fetchone() or [0])[0] or 0)
        if active_count >= MAX_ACTIVE_PER_USER:
            conn.rollback()
            return {
                "ok": False,
                "message": "你目前已有 3 張待處理生圖，請等其中一張完成或取消後再試。",
            }

        cursor.execute("""
            INSERT INTO image_generation_jobs (
                bot_id, chat_id, user_id, action_id, gender,
                generation_mode, prompt_mode, source_choice, fixed_tag,
                reference_type, reference_code, has_custom_upload,
                status, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'created',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
            RETURNING id
        """, (
            _text(bot_id), _text(chat_id), _text(user_id), int(action_id), gender,
            generation_mode, prompt_mode, source_choice, fixed_tag or None,
            reference_type, reference_code or None, bool(custom_upload),
        ))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return {"ok": False, "message": "無法建立生圖任務"}
        job_id = int(row[0])
        encrypted_source_prompt = _encrypt_prompt(job_id, final_prompt, field="source_prompt")
        encrypted_final_prompt = _encrypt_prompt(job_id, final_prompt, field="final_prompt")
        cursor.execute(
            """
            UPDATE image_generation_jobs
            SET source_prompt=%s, final_prompt=%s,
                prompt_generation_status='pending',
                prompt_chars_before=%s
            WHERE id=%s
            """,
            (encrypted_source_prompt, encrypted_final_prompt, len(str(final_prompt or "")), job_id),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("IMAGE JOB CREATE ERROR:", exc, flush=True)
        return {"ok": False, "message": "建立生圖任務失敗"}
    finally:
        conn.close()

    status_sent = send_message(
        bot_id,
        chat_id,
        "prompt生成中",
        reply_markup=_cancel_markup(job_id),
    )
    status_message_id = _extract_message_id(status_sent)
    if status_message_id:
        _update_job(job_id, status_message_id=status_message_id)
    else:
        print(f"IMAGE PROMPT STATUS SEND FAILED job_id={job_id}", flush=True)

    run_image_job_in_thread(
        job_id,
        custom_upload=custom_upload,
        custom_mask=custom_mask,
    )
    return {"ok": True, "job_id": job_id}


def _get_job(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bot_id, chat_id, user_id, action_id, gender,
                   generation_mode, prompt_mode, source_choice, fixed_tag,
                   reference_type, reference_code, has_custom_upload,
                   source_prompt, final_prompt, prompt_generation_status,
                   prompt_model, prompt_error, prompt_chars_before, prompt_chars_after,
                   status_message_id, status, horde_request_id, api_slot,
                   wait_time, queue_position, cancel_requested,
                   queued_notified, processing_notified,
                   created_at, started_at, completed_at, error_message
            FROM image_generation_jobs WHERE id=%s
        """, (int(job_id),))
        r = cursor.fetchone()
        if not r:
            return None
        keys = [
            "id", "bot_id", "chat_id", "user_id", "action_id", "gender",
            "generation_mode", "prompt_mode", "source_choice", "fixed_tag",
            "reference_type", "reference_code", "has_custom_upload",
            "source_prompt", "final_prompt", "prompt_generation_status",
            "prompt_model", "prompt_error", "prompt_chars_before", "prompt_chars_after",
            "status_message_id", "status", "horde_request_id", "api_slot",
            "wait_time", "queue_position", "cancel_requested",
            "queued_notified", "processing_notified",
            "created_at", "started_at", "completed_at", "error_message",
        ]
        return dict(zip(keys, r))
    finally:
        conn.close()


def _claim_job(job_id: int, worker_token: str) -> bool:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE image_generation_jobs
            SET worker_token=%s, heartbeat_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
              AND status = ANY(%s)
              AND (
                    worker_token IS NULL
                    OR heartbeat_at IS NULL
                    OR heartbeat_at < CURRENT_TIMESTAMP - INTERVAL '75 seconds'
              )
        """, (worker_token, int(job_id), list(ACTIVE_STATUSES)))
        ok = cursor.rowcount > 0
        conn.commit()
        return ok
    finally:
        conn.close()


def _update_job(job_id: int, **values):
    if not values:
        return
    allowed = {
        "status", "horde_request_id", "api_slot", "wait_time", "queue_position",
        "cancel_requested", "queued_notified", "processing_notified", "error_message",
        "started_at", "completed_at", "heartbeat_at", "worker_token",
        "status_message_id", "prompt_generation_status", "prompt_model", "prompt_error",
        "prompt_chars_before", "prompt_chars_after", "final_prompt",
    }
    values = {k: v for k, v in values.items() if k in allowed}
    if not values:
        return
    parts = [f"{key}=%s" for key in values]
    params = list(values.values()) + [int(job_id)]
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE image_generation_jobs SET {', '.join(parts)}, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def _elapsed_seconds(created_at) -> int:
    if not created_at:
        return 0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()))


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    minutes, secs = divmod(seconds, 60)
    if minutes:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


def _queue_text(check: Dict[str, Any], elapsed_seconds: int) -> str:
    wait_time = check.get("wait_time")
    queue_position = check.get("queue_position")

    lines = ["生圖中請稍後"]

    if isinstance(queue_position, int) and queue_position >= 0:
        lines.append(f"排隊位置：{queue_position}")
    else:
        lines.append("排隊位置：取得中")

    if isinstance(wait_time, (int, float)) and int(wait_time) >= 0:
        lines.append(f"預計等待：約 {_format_duration(int(wait_time))}")
    else:
        lines.append("預計等待：估算中")

    lines.append(f"已等待：{_format_duration(elapsed_seconds)}")
    return "\n".join(lines)


def _edit_status_message(
    job: Dict[str, Any],
    text: str,
    allow_cancel: bool = True,
) -> Optional[int]:
    message_id = job.get("status_message_id")
    reply_markup = _cancel_markup(job["id"]) if allow_cancel else {"inline_keyboard": []}
    edited = None
    if message_id:
        edited = edit_message_text(
            job["bot_id"],
            job["chat_id"],
            message_id,
            text,
            reply_markup=reply_markup,
        )

    if edited:
        return message_id

    sent = send_message(
        job["bot_id"],
        job["chat_id"],
        text,
        reply_markup=reply_markup,
    )
    new_message_id = _extract_message_id(sent)
    if new_message_id:
        _update_job(job["id"], status_message_id=new_message_id)
        job["status_message_id"] = new_message_id
    return new_message_id


def _delete_status_message(job: Dict[str, Any]) -> bool:
    message_id = job.get("status_message_id")
    if not message_id:
        return False

    deleted = delete_message(job["bot_id"], job["chat_id"], message_id)
    _update_job(job["id"], status_message_id=None)
    job["status_message_id"] = None

    print(
        f"IMAGE STATUS MESSAGE DELETE job_id={job['id']} "
        f"message_id={message_id} ok={bool(deleted)}",
        flush=True,
    )
    return bool(deleted)


def _send_result_notice(job: Dict[str, Any], text: str) -> Optional[int]:
    _delete_status_message(job)
    sent = send_message(
        job["bot_id"],
        job["chat_id"],
        text,
        reply_markup=_delete_notice_markup(job["id"]),
    )
    return _extract_message_id(sent)


def _fail(
    job: Dict[str, Any],
    message: str,
    code: str = "UNKNOWN_ERROR",
    public_text: Optional[str] = None,
):
    clean_message = _text(message) or "未知錯誤"
    clean_code = _text(code) or "UNKNOWN_ERROR"

    _update_job(
        job["id"],
        status="failed",
        error_message=f"{clean_code}: {clean_message}"[:500],
        completed_at=datetime.utcnow(),
        worker_token=None,
    )

    notice_text = _text(public_text) or f"生圖失敗：{clean_message}"
    _send_result_notice(job, f"{notice_text}\n代號：{clean_code}")


def _cancel(job: Dict[str, Any]):
    if job.get("horde_request_id"):
        cancel_image_request(job["horde_request_id"], job.get("api_slot"))
    _update_job(
        job["id"],
        status="canceled",
        error_message="USER_CANCELLED",
        completed_at=datetime.utcnow(),
        worker_token=None,
    )
    _send_result_notice(job, "生圖任務已取消\n代號：USER_CANCELLED")


def _processing_text(elapsed_seconds: int) -> str:
    # 工作節點已接單後，保留同一則狀態訊息直到圖片真的傳進聊天室。
    return "正在生圖"


def _load_system_reference(gender: Any) -> Optional[Dict[str, Any]]:
    filename = BASE_REFERENCE_FILES.get(_text(gender))
    if not filename:
        return None
    path = BASE_REFERENCE_DIR / filename
    if not path.exists() or not path.is_file():
        return None
    try:
        return {
            "bytes": path.read_bytes(),
            "mime_type": "image/png",
            "path": str(path),
        }
    except Exception as exc:
        print(f"SYSTEM REFERENCE READ ERROR gender={gender}:", exc, flush=True)
        return None


def _resolve_reference(job: Dict[str, Any], custom_upload: Optional[Dict[str, Any]]):
    if job.get("reference_type") == "custom_upload":
        return custom_upload
    if job.get("reference_type") == "chat_image":
        return download_image_asset(job.get("reference_code"), job["bot_id"], job["chat_id"])
    if job.get("reference_type") == "system_reference":
        return _load_system_reference(job.get("gender"))
    return None


def _save_generated_telegram_photo(job: Dict[str, Any], result: Dict[str, Any]) -> bool:
    message = (result or {}).get("result") or {}
    photos = message.get("photo") or []
    if not photos:
        return False
    photo = photos[-1] or {}
    saved = save_image_asset(
        bot_id=job["bot_id"],
        chat_id=job["chat_id"],
        owner_user_id=job["user_id"],
        file_id=photo.get("file_id"),
        file_unique_id=photo.get("file_unique_id"),
        telegram_message_id=message.get("message_id"),
        source_type="ai_generated",
        width=photo.get("width"),
        height=photo.get("height"),
    )
    return bool(saved)


def _job_cancel_requested(job_id: int) -> bool:
    current = _get_job(job_id) or {}
    return bool(current.get("cancel_requested"))


def _is_local_task_prompt(prompt_id: Any) -> bool:
    return str(prompt_id or "").startswith("localtask:")


def _local_task_id_from_prompt(prompt_id: Any) -> Optional[int]:
    text = str(prompt_id or "")
    if not text.startswith("localtask:"):
        return None
    try:
        return int(text.split(":", 1)[1])
    except Exception:
        return None


def _qwen_retryable_error(message: Any) -> bool:
    text = _text(message)
    retry_tokens = [
        "AI 匝道等待超過",
        "Qwen worker 沒有回傳結果",
        "建立 Qwen worker 任務失敗",
        "本機 AI 閘道設定不完整",
        "Ollama 連線失敗",
        "Qwen 閘道呼叫失敗",
    ]
    return any(token in text for token in retry_tokens)


def _wait_for_qwen_retake(job: Dict[str, Any], error_message: str) -> bool:
    elapsed = _elapsed_seconds(job.get("created_at"))
    if elapsed >= PURE_TEXT_LOCAL_QUEUE_TIMEOUT_SECONDS:
        _fail(
            job,
            "AI 匝道等待超過 24 小時，Qwen 無法補考",
            code="QWEN_RETAKE_TIMEOUT",
            public_text="生圖申請已暫存超過 24 小時，任務取消",
        )
        return False

    _update_job(
        job["id"],
        status="prompting",
        prompt_generation_status="pending",
        prompt_error=_text(error_message)[:500],
        heartbeat_at=datetime.utcnow(),
    )
    _edit_status_message(
        job,
        (
            "生圖申請已暫存\n"
            "等待 AI 匝道連線中\n"
            "重新連線後會先讓 Qwen 補考整理 prompt\n"
            "暫存期限：24 小時"
        ),
    )

    deadline = time.monotonic() + QWEN_RETRY_SECONDS
    while time.monotonic() < deadline:
        if _job_cancel_requested(job["id"]):
            _cancel(_get_job(job["id"]) or job)
            return False
        time.sleep(1)
    return True


def _finish_omi_txt2img_result(job: Dict[str, Any], waited: Dict[str, Any]) -> bool:
    if waited.get("canceled"):
        _cancel(_get_job(job["id"]) or job)
        return True
    if not waited.get("ok") or not waited.get("bytes"):
        _fail(job, waited.get("message") or "OMI 自架模型沒有回傳圖片", code="OMI_RESULT_FAILED")
        return True

    sent = send_photo_bytes(
        job["bot_id"],
        job["chat_id"],
        waited["bytes"],
        filename=f"telemini_{job['id']}.png",
        mime_type=waited.get("mime_type") or "image/png",
    )
    if not _extract_message_id(sent):
        _fail(job, "圖片已生成，但傳送到 Telegram 失敗", code="TELEGRAM_SEND_FAILED")
        return True

    _save_generated_telegram_photo(job, sent)
    _update_job(
        job["id"],
        status="completed",
        completed_at=datetime.utcnow(),
        worker_token=None,
    )
    _delete_status_message(job)
    return True


def _process_comfy_txt2img(job: Dict[str, Any]) -> bool:
    source_prompt = _decrypt_prompt(
        job["id"],
        job.get("source_prompt") or job.get("final_prompt"),
        field="source_prompt" if job.get("source_prompt") else "final_prompt",
    )
    if not source_prompt:
        _fail(job, "生圖提示詞讀取失敗", code="PROMPT_READ_FAILED")
        return True

    existing_prompt_id = _text(job.get("horde_request_id"))
    if _is_local_task_prompt(existing_prompt_id):
        if _text(job.get("prompt_generation_status")) == "fallback":
            local_task_id = _local_task_id_from_prompt(existing_prompt_id)
            if local_task_id is not None:
                try:
                    cancel_local_ai_task(local_task_id)
                except Exception as exc:
                    print(f"QWEN RETAKE CANCEL FALLBACK TASK FAILED job_id={job['id']}:", exc, flush=True)
            _update_job(
                job["id"],
                status="prompting",
                horde_request_id=None,
                api_slot=None,
                started_at=None,
                queued_notified=True,
                processing_notified=False,
                prompt_generation_status="pending",
                prompt_error="等待 AI 匝道連線後讓 Qwen 補考",
                heartbeat_at=datetime.utcnow(),
            )
            job = _get_job(job["id"]) or job
        else:
            _edit_status_message(
                job,
                (
                    "生圖申請已暫存\n"
                    "等待 AI 匝道連線中\n"
                    "開啟 OMI 自架模型後會自動開始生圖\n"
                    "暫存期限：24 小時"
                ),
            )
            waited = wait_for_prompt_image(
                existing_prompt_id,
                timeout_seconds=PURE_TEXT_LOCAL_QUEUE_TIMEOUT_SECONDS,
                cancel_check=lambda: _job_cancel_requested(job["id"]),
                progress_callback=lambda: _update_job(job["id"], heartbeat_at=datetime.utcnow()),
            )
            return _finish_omi_txt2img_result(job, waited)

    while True:
        if _job_cancel_requested(job["id"]):
            _cancel(_get_job(job["id"]) or job)
            return True

        secondary_label = get_secondary_model_label() or "qwen2.5:7b"
        organized = organize_image_prompt(source_prompt, gender_hint=job.get("gender") or "")
        organize_error = _text(organized.get("message"))
        if organized.get("ok"):
            break

        if _qwen_retryable_error(organize_error):
            if not _wait_for_qwen_retake(_get_job(job["id"]) or job, organize_error):
                return True
            job = _get_job(job["id"]) or job
            continue

        break

    if not organized.get("ok") and _qwen_retryable_error(organize_error):
        _edit_status_message(
            job,
            (
                "生圖申請已暫存\n"
                "等待 AI 匝道連線中\n"
                "重新連線後會先讓 Qwen 補考整理 prompt\n"
                "暫存期限：24 小時"
            ),
        )
        return True

    if organized.get("ok"):
        prompt_preview = organized.get("text") or organized.get("main_positive") or source_prompt
        _update_job(
            job["id"],
            final_prompt=_encrypt_prompt(job["id"], prompt_preview, field="final_prompt"),
            prompt_generation_status="ready",
            prompt_model=secondary_label,
            prompt_error=None,
            prompt_chars_before=len(source_prompt),
            prompt_chars_after=len(prompt_preview),
        )
        _edit_status_message(job, "prompt整理完成，正在送入 OMI 自架模型")
    else:
        fallback_positive = source_prompt
        fallback_negative = (
            "close-up, extreme close-up, headshot, face-only shot, portrait crop, tight crop, anime, cartoon, "
            "illustration, blurry, low quality, bad anatomy, extra limbs, malformed hands, plastic skin"
        )
        fallback_face_positive, fallback_face_negative = build_face_prompts(
            "EastAsian",
            "man" if _text(job.get("gender")).lower() == "male" else "woman",
        )
        organized = {
            "ok": True,
            "main_positive": fallback_positive,
            "main_negative": fallback_negative,
            "face_positive": fallback_face_positive,
            "face_negative": fallback_face_negative,
        }
        error_message = organize_error or "Qwen Prompt 整理失敗，已改用原始提示詞"
        _update_job(
            job["id"],
            final_prompt=_encrypt_prompt(job["id"], fallback_positive, field="final_prompt"),
            prompt_generation_status="fallback",
            prompt_model=secondary_label,
            prompt_error=error_message[:500],
            prompt_chars_before=len(source_prompt),
            prompt_chars_after=len(fallback_positive),
        )
        _edit_status_message(job, "prompt整理失敗，已改用原始提示詞，正在送入 OMI 自架模型")

    if _job_cancel_requested(job["id"]):
        _cancel(_get_job(job["id"]) or job)
        return True

    workflow = build_txt2img_workflow(
        main_positive=organized.get("main_positive") or source_prompt,
        main_negative=organized.get("main_negative") or "",
        face_positive=organized.get("face_positive") or "",
        face_negative=organized.get("face_negative") or "",
    )

    _update_job(job["id"], status="submitting", heartbeat_at=datetime.utcnow())
    queued = queue_prompt(workflow)
    if not queued.get("ok"):
        _fail(job, queued.get("message") or "OMI 自架模型任務送出失敗", code="OMI_SUBMIT_FAILED")
        return True

    prompt_id = str(queued.get("prompt_id"))
    is_local_task = _is_local_task_prompt(prompt_id)
    _update_job(
        job["id"],
        status="queued" if is_local_task else "processing",
        horde_request_id=prompt_id,
        api_slot="omi_local_worker" if is_local_task else "comfyui",
        started_at=None if is_local_task else datetime.utcnow(),
        heartbeat_at=datetime.utcnow(),
        queued_notified=True,
        processing_notified=not is_local_task,
    )
    _edit_status_message(
        job,
        (
            "生圖申請已暫存\n"
            "等待 AI 匝道連線中\n"
            "開啟 OMI 自架模型後會自動開始生圖\n"
            "暫存期限：24 小時"
        )
        if is_local_task
        else "正在生圖",
    )

    waited = wait_for_prompt_image(
        prompt_id,
        timeout_seconds=PURE_TEXT_LOCAL_QUEUE_TIMEOUT_SECONDS,
        cancel_check=lambda: _job_cancel_requested(job["id"]),
        progress_callback=lambda: _update_job(job["id"], heartbeat_at=datetime.utcnow()),
    )
    return _finish_omi_txt2img_result(job, waited)


def process_image_job(
    job_id: int,
    custom_upload: Optional[Dict[str, Any]] = None,
    custom_mask: Optional[Dict[str, Any]] = None,
):
    worker_token = secrets.token_urlsafe(12)
    if not _claim_job(job_id, worker_token):
        return

    job = _get_job(job_id)
    if not job:
        return

    last_queue_text = ""
    last_queue_update_at = 0.0

    try:
        if job.get("cancel_requested"):
            _cancel(job)
            return

        if job.get("generation_mode") == "text" and job.get("reference_type") == "system_prompt":
            if _process_comfy_txt2img(job):
                return

        if not job.get("horde_request_id"):
            # 文生圖預設不傳來源圖；若使用者在文生圖勾選啟用基準圖，
            # 則讀取 static/image_reference 下的男女基準圖，走基準圖參考生圖。
            reference = None
            if job.get("reference_type") in {"custom_upload", "chat_image", "system_reference"}:
                reference = _resolve_reference(job, custom_upload)
                if not reference or not reference.get("bytes"):
                    if job.get("reference_type") == "custom_upload":
                        _fail(job, "本次臨時上傳圖片已失效，請重新開啟生圖頁送出", code="UPLOAD_EXPIRED")
                    elif job.get("reference_type") == "chat_image":
                        _fail(job, "找不到指定的聊天室圖片，可能已被刪除", code="REFERENCE_NOT_FOUND")
                    else:
                        _fail(job, "找不到文生圖基準圖，請確認 static/image_reference 已放入男女基準圖", code="BASE_REFERENCE_NOT_FOUND")
                    return

            if job.get("generation_mode") == "mask":
                if not custom_mask or not custom_mask.get("bytes"):
                    _fail(job, "遮罩資料已失效，請重新開啟生圖頁並重新圈選修改區域", code="MASK_EXPIRED")
                    return

            source_prompt = _decrypt_prompt(
                job["id"],
                job.get("source_prompt") or job.get("final_prompt"),
                field="source_prompt" if job.get("source_prompt") else "final_prompt",
            )
            if not source_prompt:
                _fail(job, "生圖提示詞讀取失敗", code="PROMPT_READ_FAILED")
                return

            prompt_status = _text(job.get("prompt_generation_status")) or "pending"
            prompt = _decrypt_prompt(job["id"], job.get("final_prompt"), field="final_prompt")
            queue_status_text = (
                "prompt生成失敗，已改用原始提示詞送出，正在加入排隊"
                if prompt_status == "fallback"
                else "生圖任務已送出，正在加入排隊"
            )

            if prompt_status not in {"ready", "fallback"}:
                secondary_label = get_secondary_model_label() or "secondary_text_model"
                try:
                    organized = organize_image_prompt(
                        draft_prompt=source_prompt,
                        generation_mode=job.get("generation_mode") or "text",
                        reference_type=job.get("reference_type"),
                        debug_context={
                            "chat_id": job.get("chat_id"),
                            "user_id": job.get("user_id"),
                            "bot_id": job.get("bot_id"),
                            "purpose": "image_prompt",
                            "job_id": job.get("id"),
                        },
                    )
                except Exception as exc:
                    organized = {"ok": False, "message": f"副模型整理失敗：{exc}"}

                if organized.get("ok") and _text(organized.get("text")):
                    prompt = _text(organized.get("text"))
                    encrypted_prompt = _encrypt_prompt(job["id"], prompt, field="final_prompt")
                    _update_job(
                        job["id"],
                        final_prompt=encrypted_prompt,
                        prompt_generation_status="ready",
                        prompt_model=secondary_label,
                        prompt_error=None,
                        prompt_chars_before=len(source_prompt),
                        prompt_chars_after=len(prompt),
                    )
                    print(
                        "IMAGE PROMPT SECONDARY OK "
                        f"job_id={job['id']} model={secondary_label} "
                        f"input_chars={len(source_prompt)} output_chars={len(prompt)}",
                        flush=True,
                    )
                    job["prompt_generation_status"] = "ready"
                    job["prompt_model"] = secondary_label
                    queue_status_text = "prompt整理完成，正在加入排隊"
                else:
                    prompt = source_prompt
                    encrypted_prompt = _encrypt_prompt(job["id"], prompt, field="final_prompt")
                    error_message = _text(organized.get("message")) or "副模型整理失敗，已改用原始提示詞"
                    _update_job(
                        job["id"],
                        final_prompt=encrypted_prompt,
                        prompt_generation_status="fallback",
                        prompt_model=secondary_label,
                        prompt_error=error_message[:500],
                        prompt_chars_before=len(source_prompt),
                        prompt_chars_after=len(prompt),
                    )
                    print(
                        "IMAGE PROMPT SECONDARY FALLBACK "
                        f"job_id={job['id']} model={secondary_label} reason={error_message}",
                        flush=True,
                    )
                    job["prompt_generation_status"] = "fallback"
                    job["prompt_model"] = secondary_label
                    queue_status_text = "prompt整理失敗，已改用原始提示詞，正在加入排隊"
            elif not prompt:
                prompt = source_prompt

            if not prompt:
                _fail(job, "生圖提示詞整理後為空", code="PROMPT_EMPTY")
                return

            _update_job(job["id"], status="submitting", heartbeat_at=datetime.utcnow())

            prepared_reference = None
            if reference:
                try:
                    prepared_reference = prepare_img2img_source(
                        reference.get("bytes") or b"",
                        width=OUTPUT_WIDTH,
                        height=OUTPUT_HEIGHT,
                        source_mask_bytes=(custom_mask or {}).get("bytes") or b""
                        if job.get("generation_mode") == "mask"
                        else b"",
                    )
                except (RuntimeError, ValueError) as exc:
                    _fail(job, str(exc), code="IMAGE_PREPARE_FAILED")
                    return

            if prepared_reference and prepared_reference.get("mask_bytes"):
                mode = "inpainting"
            else:
                mode = "img2img" if prepared_reference else "txt2img"
            request_size = (prepared_reference or {}).get("output_size") or (OUTPUT_WIDTH, OUTPUT_HEIGHT)
            request_width, request_height = int(request_size[0]), int(request_size[1])

            print(
                "IMAGE REQUEST PREPARED "
                f"job_id={job['id']} mode={mode} "
                f"output={request_width}x{request_height} "
                f"reference_type={job.get('reference_type')} "
                f"original_size={(prepared_reference or {}).get('original_size')} "
                f"content_size={(prepared_reference or {}).get('content_size')} "
                f"pad_color={(prepared_reference or {}).get('pad_color')} "
                f"mask_coverage={(prepared_reference or {}).get('mask_coverage')} "
                f"mask_blur={(prepared_reference or {}).get('mask_blur_radius')}",
                flush=True,
            )

            request_profile = (
                "text_reference" if job.get("generation_mode") == "text" and job.get("reference_type") == "system_reference"
                else ("mask_edit" if job.get("generation_mode") == "mask" else ("image_edit" if job.get("generation_mode") == "image" else "text"))
            )

            submitted = submit_image_request(
                job_id=job["id"],
                prompt=prompt,
                source_image_bytes=(prepared_reference or {}).get("bytes") or b"",
                source_mime_type=(prepared_reference or {}).get("mime_type") or "image/png",
                source_mask_bytes=(prepared_reference or {}).get("mask_bytes") or b"",
                source_mask_mime_type=(prepared_reference or {}).get("mask_mime_type") or "image/png",
                width=request_width,
                height=request_height,
                request_profile=request_profile,
            )
            if not submitted.get("ok"):
                _fail(job, submitted.get("message") or "其他生圖功能暫時無法送出", code="SUBMIT_FAILED")
                return

            initial_queue_text = _queue_text({}, _elapsed_seconds(job.get("created_at")))
            _edit_status_message(job, initial_queue_text)
            last_queue_text = initial_queue_text
            last_queue_update_at = time.monotonic()

            _update_job(
                job["id"],
                status="queued",
                horde_request_id=submitted.get("request_id"),
                api_slot=submitted.get("api_slot"),
                queued_notified=True,
                heartbeat_at=datetime.utcnow(),
            )
            job = _get_job(job["id"])

        while True:
            job = _get_job(job_id)
            if not job:
                return

            if job.get("cancel_requested"):
                _cancel(job)
                return

            queue_elapsed = _elapsed_seconds(job.get("created_at"))
            has_started_processing = bool(job.get("started_at")) or job.get("status") == "processing"
            if not has_started_processing and queue_elapsed >= QUEUE_TIMEOUT_SECONDS:
                if job.get("horde_request_id"):
                    cancel_image_request(job["horde_request_id"], job.get("api_slot"))
                _fail(
                    job,
                    "排隊超過 30 分鐘仍未開始生成",
                    code="QUEUE_TIMEOUT",
                    public_text="生圖超過30分鐘，任務取消",
                )
                return

            check = check_image_request(job.get("horde_request_id"), job.get("api_slot"))
            if not check.get("ok"):
                status_code = check.get("status_code")
                if status_code == 404:
                    _fail(job, "找不到這個舊版生圖任務", code="LEGACY_JOB_NOT_FOUND")
                    return
                _update_job(job_id, heartbeat_at=datetime.utcnow())
                time.sleep(POLL_SECONDS)
                continue

            wait_time = check.get("wait_time")
            queue_position = check.get("queue_position")
            _update_job(
                job_id,
                wait_time=int(wait_time) if isinstance(wait_time, (int, float)) else None,
                queue_position=int(queue_position) if isinstance(queue_position, int) else None,
                heartbeat_at=datetime.utcnow(),
            )

            processing = int(check.get("processing") or 0)
            if processing > 0:
                newly_started = not (job.get("started_at") or job.get("status") == "processing")
                if newly_started:
                    _update_job(
                        job_id,
                        status="processing",
                        processing_notified=True,
                        started_at=datetime.utcnow(),
                        heartbeat_at=datetime.utcnow(),
                    )
                    processing_text = _processing_text(queue_elapsed)
                    _edit_status_message(job, processing_text)
                    last_queue_text = processing_text
                    last_queue_update_at = time.monotonic()
                job = _get_job(job_id) or job
                if newly_started:
                    print(
                        f"IMAGE GENERATION STARTED job_id={job_id} "
                        f"queue_elapsed={queue_elapsed}",
                        flush=True,
                    )
            elif not (job.get("started_at") or job.get("status") == "processing"):
                queue_text = _queue_text(check, queue_elapsed)
                now_monotonic = time.monotonic()
                should_refresh = (
                    not last_queue_text
                    or now_monotonic - last_queue_update_at >= STATUS_UPDATE_SECONDS
                )
                if should_refresh and queue_text != last_queue_text:
                    _edit_status_message(job, queue_text)
                    last_queue_text = queue_text
                    last_queue_update_at = now_monotonic
                    _update_job(job_id, queued_notified=True)

            if check.get("faulted"):
                _fail(job, "舊版生圖任務回報異常", code="LEGACY_JOB_FAULTED")
                return

            if check.get("is_possible") is False and not (job.get("started_at") or job.get("status") == "processing"):
                # 只代表目前沒有 worker 接單，任務仍留在佇列中等待。
                # 對使用者只顯示一般排隊資訊，不顯示節點相容性細節。
                _update_job(
                    job_id,
                    status="queued",
                    heartbeat_at=datetime.utcnow(),
                )

            if check.get("done"):
                # 先取得、下載並傳送圖片；只有 Telegram 確實收到圖片後，
                # 才刪除「正在生圖」狀態，避免中間出現無提示空窗。
                status = get_image_result(job.get("horde_request_id"), job.get("api_slot"))
                if not status.get("ok"):
                    _fail(job, status.get("message") or "取得圖片結果失敗", code="RESULT_FETCH_FAILED")
                    return

                generations = status.get("generations") or []
                generation = generations[0] if generations else None
                if not generation:
                    _fail(job, "舊版生圖服務沒有回傳圖片", code="RESULT_EMPTY")
                    return

                image = download_generated_image(generation.get("img"))
                if not image or not image.get("bytes"):
                    _fail(job, "生成完成，但圖片下載失敗", code="IMAGE_DOWNLOAD_FAILED")
                    return

                sent = send_photo_bytes(
                    job["bot_id"],
                    job["chat_id"],
                    image["bytes"],
                    filename=f"telemini_{job_id}.png",
                    mime_type=image.get("mime_type") or "image/png",
                )
                if not _extract_message_id(sent):
                    _fail(job, "圖片已生成，但傳送到 Telegram 失敗", code="TELEGRAM_SEND_FAILED")
                    return

                _save_generated_telegram_photo(job, sent)
                _update_job(
                    job_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                    worker_token=None,
                )
                _delete_status_message(job)
                return

            time.sleep(POLL_SECONDS)
    except Exception as exc:
        print(f"IMAGE JOB ERROR job_id={job_id}:", exc, flush=True)
        current = _get_job(job_id) or job
        _fail(current, "生圖流程發生未預期錯誤，請查看 Render log", code="UNEXPECTED_ERROR")


def run_image_job_in_thread(
    job_id: int,
    custom_upload: Optional[Dict[str, Any]] = None,
    custom_mask: Optional[Dict[str, Any]] = None,
):
    threading.Thread(
        target=process_image_job,
        args=(int(job_id), custom_upload, custom_mask),
        daemon=True,
    ).start()


def cancel_job_for_user(job_id: Any, user_id: Any, bot_id: Any, chat_id: Any) -> Dict[str, Any]:
    try:
        job_id = int(job_id)
    except Exception:
        return {"ok": False, "message": "任務代號錯誤"}

    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT status FROM image_generation_jobs
            WHERE id=%s AND user_id=%s AND bot_id=%s AND chat_id=%s
        """, (job_id, _text(user_id), _text(bot_id), _text(chat_id)))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "message": "找不到這個生圖任務"}
        if row[0] not in ACTIVE_STATUSES:
            return {"ok": False, "message": "這個任務已經結束，無法取消"}
        cursor.execute("""
            UPDATE image_generation_jobs
            SET cancel_requested=TRUE, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (job_id,))
        conn.commit()
        return {"ok": True, "message": "已送出取消生圖要求"}
    finally:
        conn.close()


def recover_active_image_jobs():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE image_generation_jobs
            SET worker_token=NULL
            WHERE status = ANY(%s)
              AND (heartbeat_at IS NULL OR heartbeat_at < CURRENT_TIMESTAMP - INTERVAL '75 seconds')
        """, (list(ACTIVE_STATUSES),))
        cursor.execute("""
            SELECT id FROM image_generation_jobs
            WHERE status = ANY(%s)
            ORDER BY id ASC
            LIMIT 100
        """, (list(ACTIVE_STATUSES),))
        ids = [int(row[0]) for row in cursor.fetchall()]
        conn.commit()
    finally:
        conn.close()

    for job_id in ids:
        run_image_job_in_thread(job_id)
