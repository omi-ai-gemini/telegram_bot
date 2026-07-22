from datetime import datetime
from typing import Any, Callable, Dict, Optional
from services.comfyui_service import build_txt2img_workflow, queue_prompt, wait_for_prompt_image

class ImageTaskContext:
    def __init__(self, *, text: Callable[[Any], str], decrypt_prompt: Callable[..., str], encrypt_prompt: Callable[..., str], update_job: Callable[..., None], get_job: Callable[[int], Optional[Dict[str, Any]]], job_cancel_requested: Callable[[int], bool], cancel_job: Callable[[Dict[str, Any]], None], fail_job: Callable[..., None], edit_status_message: Callable[..., Any], finish_omi_txt2img_result: Callable[[Dict[str, Any], Dict[str, Any]], bool], is_local_task_prompt: Callable[[Any], bool], local_task_id_from_prompt: Callable[[Any], Optional[int]], pure_text_queue_timeout_seconds: int, **_):
        self.text=text; self.decrypt_prompt=decrypt_prompt; self.encrypt_prompt=encrypt_prompt; self.update_job=update_job; self.get_job=get_job; self.job_cancel_requested=job_cancel_requested; self.cancel_job=cancel_job; self.fail_job=fail_job; self.edit_status_message=edit_status_message; self.finish_omi_txt2img_result=finish_omi_txt2img_result; self.is_local_task_prompt=is_local_task_prompt; self.local_task_id_from_prompt=local_task_id_from_prompt; self.pure_text_queue_timeout_seconds=int(pure_text_queue_timeout_seconds)
    def current_job(self, job): return self.get_job(int(job["id"])) or job
    def heartbeat(self, job_id): self.update_job(job_id, heartbeat_at=datetime.utcnow())
    def cancel_requested(self, job_id): return self.job_cancel_requested(job_id)
    def cancel_current(self, job): self.cancel_job(self.current_job(job)); return True

def _offline_prompt_text():
    return "生圖申請已暫存\n等待 AI 匝道連線中\n開啟 OMI 自架模型後會自動開始生圖\n暫存期限：24 小時"

def process_pure_text_omi_job(job: Dict[str, Any], ctx: ImageTaskContext) -> bool:
    source_prompt = ctx.decrypt_prompt(job["id"], job.get("source_prompt") or job.get("final_prompt"), field="source_prompt" if job.get("source_prompt") else "final_prompt")
    if not source_prompt:
        ctx.fail_job(job, "生圖提示詞讀取失敗", code="PROMPT_READ_FAILED"); return True
    if ctx.cancel_requested(int(job["id"])): return ctx.cancel_current(job)
    ctx.update_job(job["id"], final_prompt=ctx.encrypt_prompt(job["id"], source_prompt, field="final_prompt"), prompt_generation_status="ready", prompt_model="direct_prompt", prompt_error=None, prompt_chars_before=len(source_prompt), prompt_chars_after=len(source_prompt))
    ctx.edit_status_message(job, "正在送入 OMI 自架模型")
    workflow = build_txt2img_workflow(main_positive=source_prompt, main_negative="", face_positive="", face_negative="")
    ctx.update_job(job["id"], status="submitting", heartbeat_at=datetime.utcnow())
    queued = queue_prompt(workflow)
    if not queued.get("ok"):
        ctx.fail_job(job, queued.get("message") or "OMI 自架模型任務送出失敗", code="OMI_SUBMIT_FAILED"); return True
    prompt_id=str(queued.get("prompt_id")); local=ctx.is_local_task_prompt(prompt_id)
    ctx.update_job(job["id"], status="queued" if local else "processing", horde_request_id=prompt_id, api_slot="omi_local_worker" if local else "comfyui", started_at=None if local else datetime.utcnow(), heartbeat_at=datetime.utcnow(), queued_notified=True, processing_notified=not local)
    ctx.edit_status_message(job, _offline_prompt_text() if local else "正在生圖")
    waited=wait_for_prompt_image(prompt_id, timeout_seconds=ctx.pure_text_queue_timeout_seconds, cancel_check=lambda: ctx.cancel_requested(int(job["id"])), progress_callback=lambda: ctx.heartbeat(int(job["id"])))
    return ctx.finish_omi_txt2img_result(job, waited)
