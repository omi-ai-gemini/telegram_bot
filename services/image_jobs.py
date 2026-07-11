import secrets
import threading
import time
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
from services.database import get_conn
from services.image_prepare import OUTPUT_HEIGHT, OUTPUT_WIDTH, prepare_img2img_source
from services.image_store import download_image_asset, save_image_asset
from services.telegram_service import send_message, send_photo_bytes


ACTIVE_STATUSES = ("created", "submitting", "queued", "processing")
MAX_ACTIVE_PER_USER = 3
JOB_TIMEOUT_SECONDS = 20 * 60
POLL_SECONDS = 4


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


def _encrypt_prompt(job_id: int, prompt: str) -> str:
    try:
        return encrypt_text(prompt, aad=aad_for("image_generation_jobs", "final_prompt", job_id))
    except Exception as exc:
        print("IMAGE PROMPT ENCRYPT ERROR:", exc, flush=True)
        return prompt


def _decrypt_prompt(job_id: int, value: str) -> str:
    if not is_encrypted(value):
        return _text(value)
    try:
        return decrypt_text(value, aad=aad_for("image_generation_jobs", "final_prompt", job_id))
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
        cursor.execute(
            "UPDATE image_generation_jobs SET final_prompt=%s WHERE id=%s",
            (_encrypt_prompt(job_id, final_prompt), job_id),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("IMAGE JOB CREATE ERROR:", exc, flush=True)
        return {"ok": False, "message": "建立生圖任務失敗"}
    finally:
        conn.close()

    send_message(
        bot_id,
        chat_id,
        "生圖任務已送出，正在加入排隊。",
        reply_markup=_cancel_markup(job_id),
    )
    run_image_job_in_thread(job_id, custom_upload=custom_upload)
    return {"ok": True, "job_id": job_id}


def _get_job(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bot_id, chat_id, user_id, action_id, gender,
                   generation_mode, prompt_mode, source_choice, fixed_tag,
                   reference_type, reference_code, has_custom_upload,
                   final_prompt, status, horde_request_id, api_slot,
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
            "final_prompt", "status", "horde_request_id", "api_slot",
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


def _queue_text(check: Dict[str, Any]) -> str:
    wait_time = check.get("wait_time")
    queue_position = check.get("queue_position")
    lines = ["生圖中請稍後"]
    if isinstance(wait_time, (int, float)) and int(wait_time) >= 0:
        lines.append(f"預計等待約 {_format_duration(int(wait_time))}")
    else:
        lines.append("目前無法估算等待時間")
    if isinstance(queue_position, int) and queue_position >= 0:
        lines.append(f"目前排隊位置：{queue_position}")
    return "\n".join(lines)


def _fail(job: Dict[str, Any], message: str):
    _update_job(
        job["id"],
        status="failed",
        error_message=_text(message)[:500],
        completed_at=datetime.utcnow(),
        worker_token=None,
    )
    send_message(job["bot_id"], job["chat_id"], f"生圖失敗：{_text(message) or '未知錯誤'}")


def _cancel(job: Dict[str, Any]):
    if job.get("horde_request_id"):
        cancel_image_request(job["horde_request_id"], job.get("api_slot"))
    _update_job(
        job["id"],
        status="canceled",
        completed_at=datetime.utcnow(),
        worker_token=None,
    )
    send_message(job["bot_id"], job["chat_id"], "生圖已取消")


def _resolve_reference(job: Dict[str, Any], custom_upload: Optional[Dict[str, Any]]):
    if job.get("reference_type") == "custom_upload":
        return custom_upload
    if job.get("reference_type") == "chat_image":
        return download_image_asset(job.get("reference_code"), job["bot_id"], job["chat_id"])
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


def process_image_job(job_id: int, custom_upload: Optional[Dict[str, Any]] = None):
    worker_token = secrets.token_urlsafe(12)
    if not _claim_job(job_id, worker_token):
        return

    job = _get_job(job_id)
    if not job:
        return

    try:
        if job.get("cancel_requested"):
            _cancel(job)
            return

        if not job.get("horde_request_id"):
            # 文生圖不傳來源圖；圖生圖只讀玩家上傳或聊天室圖片。
            # 舊版 system_reference 任務不再使用，避免重新進入遮罩流程。
            if job.get("reference_type") == "system_reference":
                _fail(job, "生圖流程已更新，請重新開啟生圖頁送出任務")
                return

            reference = None
            if job.get("reference_type") in {"custom_upload", "chat_image"}:
                reference = _resolve_reference(job, custom_upload)
                if not reference or not reference.get("bytes"):
                    if job.get("reference_type") == "custom_upload":
                        _fail(job, "本次臨時上傳圖片已失效，請重新開啟生圖頁送出")
                    else:
                        _fail(job, "找不到指定的聊天室圖片，可能已被刪除")
                    return

            prompt = _decrypt_prompt(job["id"], job.get("final_prompt"))
            if not prompt:
                _fail(job, "生圖提示詞讀取失敗")
                return

            _update_job(job["id"], status="submitting", started_at=datetime.utcnow(), heartbeat_at=datetime.utcnow())

            prepared_reference = None
            if reference:
                try:
                    prepared_reference = prepare_img2img_source(
                        reference.get("bytes") or b"",
                        width=OUTPUT_WIDTH,
                        height=OUTPUT_HEIGHT,
                    )
                except (RuntimeError, ValueError) as exc:
                    _fail(job, str(exc))
                    return

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
                f"pad_color={(prepared_reference or {}).get('pad_color')}",
                flush=True,
            )

            submitted = submit_image_request(
                job_id=job["id"],
                prompt=prompt,
                source_image_bytes=(prepared_reference or {}).get("bytes") or b"",
                source_mime_type=(prepared_reference or {}).get("mime_type") or "image/png",
                width=request_width,
                height=request_height,
            )
            if not submitted.get("ok"):
                _fail(job, submitted.get("message") or "AI Horde 拒絕任務")
                return

            _update_job(
                job["id"],
                status="queued",
                horde_request_id=submitted.get("request_id"),
                api_slot=submitted.get("api_slot"),
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

            if _elapsed_seconds(job.get("created_at")) >= JOB_TIMEOUT_SECONDS:
                if job.get("horde_request_id"):
                    cancel_image_request(job["horde_request_id"], job.get("api_slot"))
                _fail(job, "排隊與生成時間超過 20 分鐘，任務已停止")
                return

            check = check_image_request(job.get("horde_request_id"), job.get("api_slot"))
            if not check.get("ok"):
                status_code = check.get("status_code")
                if status_code == 404:
                    _fail(job, "AI Horde 找不到這個任務")
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

            if not job.get("queued_notified"):
                send_message(
                    job["bot_id"],
                    job["chat_id"],
                    _queue_text(check),
                    reply_markup=_cancel_markup(job_id),
                )
                _update_job(job_id, queued_notified=True)

            processing = int(check.get("processing") or 0)
            if processing > 0 and not job.get("processing_notified"):
                send_message(
                    job["bot_id"],
                    job["chat_id"],
                    "生圖中請稍後",
                    reply_markup=_cancel_markup(job_id),
                )
                _update_job(job_id, status="processing", processing_notified=True)

            if check.get("faulted"):
                _fail(job, "AI Horde 回報任務異常")
                return

            if check.get("is_possible") is False:
                _fail(job, "目前沒有可執行此模型與尺寸的工作節點")
                return

            if check.get("done"):
                status = get_image_result(job.get("horde_request_id"), job.get("api_slot"))
                if not status.get("ok"):
                    _fail(job, status.get("message") or "取得圖片結果失敗")
                    return

                generations = status.get("generations") or []
                generation = generations[0] if generations else None
                if not generation:
                    _fail(job, "AI Horde 沒有回傳圖片")
                    return

                image = download_generated_image(generation.get("img"))
                if not image or not image.get("bytes"):
                    _fail(job, "生成完成，但圖片下載失敗")
                    return

                sent = send_photo_bytes(
                    job["bot_id"],
                    job["chat_id"],
                    image["bytes"],
                    filename=f"telemini_{job_id}.png",
                    mime_type=image.get("mime_type") or "image/png",
                )
                if not _extract_message_id(sent):
                    _fail(job, "圖片已生成，但傳送到 Telegram 失敗")
                    return

                _save_generated_telegram_photo(job, sent)
                _update_job(
                    job_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                    worker_token=None,
                )
                return

            time.sleep(POLL_SECONDS)
    except Exception as exc:
        print(f"IMAGE JOB ERROR job_id={job_id}:", exc, flush=True)
        current = _get_job(job_id) or job
        _fail(current, "生圖流程發生未預期錯誤，請查看 Render log")


def run_image_job_in_thread(job_id: int, custom_upload: Optional[Dict[str, Any]] = None):
    threading.Thread(
        target=process_image_job,
        args=(int(job_id), custom_upload),
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
