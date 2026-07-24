import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from services.comfyui_service import build_txt2img_workflow, queue_prompt, wait_for_prompt_image
from services.local_ai_tasks import cancel_local_ai_task
from services.qwen_service import get_secondary_model_label, organize_image_prompt


class ImageTaskContext:
    def __init__(
        self,
        *,
        text: Callable[[Any], str],
        decrypt_prompt: Callable[..., str],
        encrypt_prompt: Callable[..., str],
        update_job: Callable[..., None],
        get_job: Callable[[int], Optional[Dict[str, Any]]],
        job_cancel_requested: Callable[[int], bool],
        cancel_job: Callable[[Dict[str, Any]], None],
        fail_job: Callable[..., None],
        edit_status_message: Callable[..., Any],
        finish_omi_txt2img_result: Callable[[Dict[str, Any], Dict[str, Any]], bool],
        is_local_task_prompt: Callable[[Any], bool],
        local_task_id_from_prompt: Callable[[Any], Optional[int]],
        qwen_retryable_error: Callable[[Any], bool],
        wait_for_qwen_retake: Callable[[Dict[str, Any], str], bool],
        pure_text_queue_timeout_seconds: int,
    ):
        self.text = text
        self.decrypt_prompt = decrypt_prompt
        self.encrypt_prompt = encrypt_prompt
        self.update_job = update_job
        self.get_job = get_job
        self.job_cancel_requested = job_cancel_requested
        self.cancel_job = cancel_job
        self.fail_job = fail_job
        self.edit_status_message = edit_status_message
        self.finish_omi_txt2img_result = finish_omi_txt2img_result
        self.is_local_task_prompt = is_local_task_prompt
        self.local_task_id_from_prompt = local_task_id_from_prompt
        self.qwen_retryable_error = qwen_retryable_error
        self.wait_for_qwen_retake = wait_for_qwen_retake
        self.pure_text_queue_timeout_seconds = int(pure_text_queue_timeout_seconds)

    def current_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return self.get_job(int(job["id"])) or job

    def heartbeat(self, job_id: int) -> None:
        self.update_job(job_id, heartbeat_at=datetime.utcnow())

    def cancel_requested(self, job_id: int) -> bool:
        return self.job_cancel_requested(job_id)

    def cancel_current(self, job: Dict[str, Any]) -> bool:
        self.cancel_job(self.current_job(job))
        return True


def _offline_prompt_text(*, qwen_retake: bool = False) -> str:
    lines = [
        "生圖申請已暫存",
        "等待 AI 匝道連線中",
    ]
    if qwen_retake:
        lines.append("重新連線後會先讓 Qwen 補考整理 prompt")
    else:
        lines.append("開啟 OMI 自架模型後會自動開始生圖")
    lines.append("暫存期限：24 小時")
    return "\n".join(lines)


def _cancel_fallback_local_task(job: Dict[str, Any], ctx: ImageTaskContext) -> None:
    local_task_id = ctx.local_task_id_from_prompt(job.get("horde_request_id"))
    if local_task_id is None:
        return
    try:
        cancel_local_ai_task(local_task_id)
    except Exception as exc:
        print(
            f"IMAGE TASK MANAGER CANCEL FALLBACK TASK FAILED job_id={job.get('id')} task_id={local_task_id}:",
            exc,
            flush=True,
        )


def _wait_existing_omi_task(job: Dict[str, Any], ctx: ImageTaskContext) -> bool:
    ctx.edit_status_message(job, _offline_prompt_text(qwen_retake=False))
    waited = wait_for_prompt_image(
        ctx.text(job.get("horde_request_id")),
        timeout_seconds=ctx.pure_text_queue_timeout_seconds,
        cancel_check=lambda: ctx.cancel_requested(int(job["id"])),
        progress_callback=lambda: ctx.heartbeat(int(job["id"])),
    )
    return ctx.finish_omi_txt2img_result(job, waited)


def _organize_prompt_with_retake(
    job: Dict[str, Any],
    source_prompt: str,
    ctx: ImageTaskContext,
) -> Optional[Dict[str, Any]]:
    while True:
        if ctx.cancel_requested(int(job["id"])):
            ctx.cancel_current(job)
            return None

        secondary_label = get_secondary_model_label() or "qwen2.5:7b"
        organized = organize_image_prompt(
            source_prompt,
            gender_hint=job.get("gender") or "",
            cancel_check=lambda: ctx.cancel_requested(int(job["id"])),
            progress_callback=lambda: ctx.heartbeat(int(job["id"])),
        )
        if organized.get("canceled") or ctx.cancel_requested(int(job["id"])):
            ctx.cancel_current(job)
            return None

        organize_error = ctx.text(organized.get("message"))
        if organized.get("ok"):
            organized["prompt_model"] = secondary_label
            return organized

        if ctx.qwen_retryable_error(organize_error):
            if not ctx.wait_for_qwen_retake(ctx.current_job(job), organize_error):
                return None
            job = ctx.current_job(job)
            continue

        if not ctx.wait_for_qwen_retake(
            ctx.current_job(job),
            organize_error or "Qwen Prompt 整理失敗，已暫存等待補考",
        ):
            return None
        return None


def process_pure_text_omi_job(job: Dict[str, Any], ctx: ImageTaskContext) -> bool:
    source_prompt = ctx.decrypt_prompt(
        job["id"],
        job.get("source_prompt") or job.get("final_prompt"),
        field="source_prompt" if job.get("source_prompt") else "final_prompt",
    )
    if not source_prompt:
        ctx.fail_job(job, "生圖提示詞讀取失敗", code="PROMPT_READ_FAILED")
        return True

    existing_prompt_id = ctx.text(job.get("horde_request_id"))
    if ctx.is_local_task_prompt(existing_prompt_id):
        if ctx.text(job.get("prompt_generation_status")) == "fallback":
            _cancel_fallback_local_task(job, ctx)
            ctx.update_job(
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
            job = ctx.current_job(job)
        else:
            return _wait_existing_omi_task(job, ctx)

    organized = _organize_prompt_with_retake(job, source_prompt, ctx)
    if not organized:
        return True

    prompt_preview = (
        organized.get("preview_text")
        or organized.get("text")
        or organized.get("main_positive")
        or source_prompt
    )
    ctx.update_job(
        job["id"],
        final_prompt=ctx.encrypt_prompt(job["id"], prompt_preview, field="final_prompt"),
        prompt_generation_status="ready",
        prompt_model=organized.get("prompt_model") or get_secondary_model_label() or "qwen2.5:7b",
        prompt_error=None,
        prompt_chars_before=len(source_prompt),
        prompt_chars_after=len(prompt_preview),
    )
    ctx.edit_status_message(job, "prompt整理完成，正在送入 OMI 自架模型")

    if ctx.cancel_requested(int(job["id"])):
        return ctx.cancel_current(job)

    workflow = build_txt2img_workflow(
        main_positive=organized.get("main_positive") or source_prompt,
        main_negative=organized.get("main_negative") or "",
        face_positive=organized.get("face_positive") or "",
        face_negative=organized.get("face_negative") or "",
    )

    ctx.update_job(job["id"], status="submitting", heartbeat_at=datetime.utcnow())
    queued = queue_prompt(workflow)
    if not queued.get("ok"):
        ctx.fail_job(job, queued.get("message") or "OMI 自架模型任務送出失敗", code="OMI_SUBMIT_FAILED")
        return True

    prompt_id = str(queued.get("prompt_id"))
    is_local_task = ctx.is_local_task_prompt(prompt_id)
    ctx.update_job(
        job["id"],
        status="queued" if is_local_task else "processing",
        horde_request_id=prompt_id,
        api_slot="omi_local_worker" if is_local_task else "comfyui",
        started_at=None if is_local_task else datetime.utcnow(),
        heartbeat_at=datetime.utcnow(),
        queued_notified=True,
        processing_notified=not is_local_task,
    )
    ctx.edit_status_message(
        job,
        _offline_prompt_text(qwen_retake=False) if is_local_task else "正在生圖",
    )

    waited = wait_for_prompt_image(
        prompt_id,
        timeout_seconds=ctx.pure_text_queue_timeout_seconds,
        cancel_check=lambda: ctx.cancel_requested(int(job["id"])),
        progress_callback=lambda: ctx.heartbeat(int(job["id"])),
    )
    return ctx.finish_omi_txt2img_result(job, waited)
