from datetime import datetime

from flask import Blueprint, Response, jsonify, render_template, request

from services.image_actions import load_action_context
from services.image_auth import verify_image_token
from services.image_jobs import create_image_job
from services.image_prompt import FIXED_TAGS, build_image_prompt
from services.image_store import (
    delete_image_asset,
    download_image_asset,
    get_image_asset,
    list_image_assets,
    rename_image_asset,
)


image_gen_bp = Blueprint("image_gen", __name__)
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_UPLOAD_MIMES = {"image/jpeg", "image/png", "image/webp"}


def _token():
    return request.values.get("token", "")


def _auth(page_type):
    auth = verify_image_token(_token(), expected_page=page_type)
    if not auth.get("ok"):
        return auth, (auth.get("message") or "連結驗證失敗", 403)
    return auth, None


def _render_generate(auth, context=None, error="", success="", job_id=None, form=None, status=200):
    return render_template(
        "image_gen_form.html",
        token=_token(),
        auth=auth,
        context=context or {},
        fixed_tags=list(FIXED_TAGS.keys()),
        error=error,
        success=success,
        job_id=job_id,
        form=form or {},
        expires_at=auth.get("expires_at", 0),
    ), status


@image_gen_bp.route("/image/generate", methods=["GET"])
def image_generate_page():
    auth, error = _auth("generate")
    if error:
        return error
    context = load_action_context(
        auth.get("action_id"), auth["user_id"], auth["bot_id"], auth["chat_id"]
    )
    if not context:
        return "找不到這輪對話，請回 Telegram 重新開啟生圖設定", 404
    return _render_generate(auth, context=context)


@image_gen_bp.route("/image/generate", methods=["POST"])
def image_generate_submit():
    auth, error = _auth("generate")
    if error:
        return error

    context = load_action_context(
        auth.get("action_id"), auth["user_id"], auth["bot_id"], auth["chat_id"]
    )
    if not context:
        return "找不到這輪對話，請回 Telegram 重新開啟生圖設定", 404

    form = request.form.to_dict()
    raw_mode = str(form.get("generation_mode") or "text").strip()
    # 舊表單相容：default=文生圖、custom=圖生圖。
    generation_mode = {"default": "text", "custom": "image"}.get(raw_mode, raw_mode)
    gender = str(form.get("gender") or "").strip()
    prompt_mode = str(form.get("prompt_mode") or "tag").strip()
    source_choice = str(form.get("source_choice") or "ai").strip()
    fixed_tag = str(form.get("fixed_tag") or "").strip()
    supplement_prompt = str(form.get("supplement_prompt") or "").strip()
    custom_prompt = str(form.get("custom_prompt") or "").strip()
    reference_code = str(form.get("reference_code") or "").strip()

    if generation_mode not in {"text", "image"}:
        return _render_generate(auth, context, error="生圖模式錯誤", form=form, status=400)
    if generation_mode == "text" and gender not in {"male", "female"}:
        return _render_generate(auth, context, error="文生圖必須選擇人物性別", form=form, status=400)
    if prompt_mode not in {"tag", "custom"}:
        return _render_generate(auth, context, error="提示詞模式錯誤", form=form, status=400)
    if source_choice not in {"user", "ai"}:
        return _render_generate(auth, context, error="本輪訊息來源錯誤", form=form, status=400)

    custom_upload = None
    reference_type = "system_prompt"

    if generation_mode == "image":
        upload = request.files.get("source_image")

        # 圖生圖可使用本次上傳圖或聊天室圖片代號；同時提供時以上傳圖優先。
        if upload and upload.filename:
            mime_type = str(upload.mimetype or "").lower()
            if mime_type not in ALLOWED_UPLOAD_MIMES:
                return _render_generate(auth, context, error="只支援 JPG、PNG、WEBP", form=form, status=400)
            raw = upload.read(MAX_UPLOAD_BYTES + 1)
            if not raw or len(raw) > MAX_UPLOAD_BYTES:
                return _render_generate(auth, context, error="圖片不可超過 12MB", form=form, status=400)
            custom_upload = {"bytes": raw, "mime_type": mime_type}
            reference_type = "custom_upload"
            reference_code = ""
        elif reference_code:
            asset = get_image_asset(reference_code, auth["bot_id"], auth["chat_id"])
            if not asset:
                return _render_generate(auth, context, error="找不到指定的聊天室圖片代號或名稱", form=form, status=400)
            reference_type = "chat_image"
            reference_code = asset.get("image_code")
        else:
            return _render_generate(
                auth,
                context,
                error="圖生圖必須上傳圖片，或填入聊天室圖片代號／名稱",
                form=form,
                status=400,
            )

    source_text = context.get("user_text") if source_choice == "user" else context.get("assistant_text")
    try:
        final_prompt = build_image_prompt(
            source_text=source_text,
            prompt_mode=prompt_mode,
            generation_mode=generation_mode,
            gender=gender,
            fixed_tag=fixed_tag,
            supplement_prompt=supplement_prompt,
            custom_prompt=custom_prompt,
        )
    except ValueError as exc:
        return _render_generate(auth, context, error=str(exc), form=form, status=400)

    created = create_image_job(
        user_id=auth["user_id"],
        bot_id=auth["bot_id"],
        chat_id=auth["chat_id"],
        action_id=auth.get("action_id"),
        gender=gender or "reference",
        generation_mode=generation_mode,
        prompt_mode=prompt_mode,
        source_choice=source_choice,
        fixed_tag=fixed_tag,
        final_prompt=final_prompt,
        reference_type=reference_type,
        reference_code=reference_code or None,
        custom_upload=custom_upload,
    )
    if not created.get("ok"):
        return _render_generate(auth, context, error=created.get("message") or "任務建立失敗", form=form, status=400)

    return _render_generate(
        auth,
        context,
        success="prompt生成中，請回 Telegram 查看狀態。",
        job_id=created.get("job_id"),
        form=form,
    )


@image_gen_bp.route("/setting/images", methods=["GET"])
def image_library_page():
    auth, error = _auth("library")
    if error:
        return error
    items = list_image_assets(auth["bot_id"], auth["chat_id"], limit=100)
    return render_template(
        "image_library.html",
        token=_token(),
        auth=auth,
        items=items,
        message=request.args.get("message", ""),
        expires_at=auth.get("expires_at", 0),
    )


@image_gen_bp.route("/setting/images/preview/<identifier>", methods=["GET"])
def image_library_preview(identifier):
    auth, error = _auth("library")
    if error:
        return error
    media = download_image_asset(identifier, auth["bot_id"], auth["chat_id"])
    if not media:
        return "圖片讀取失敗", 404
    return Response(media["bytes"], mimetype=media.get("mime_type") or "image/jpeg", headers={"Cache-Control": "private, max-age=60"})


@image_gen_bp.route("/setting/images/rename", methods=["POST"])
def image_library_rename():
    auth, error = _auth("library")
    if error:
        return error
    result = rename_image_asset(
        request.form.get("identifier"),
        request.form.get("alias", ""),
        auth["bot_id"],
        auth["chat_id"],
    )
    items = list_image_assets(auth["bot_id"], auth["chat_id"], limit=100)
    return render_template(
        "image_library.html",
        token=_token(), auth=auth, items=items,
        message=result.get("message", ""), expires_at=auth.get("expires_at", 0),
    ), (200 if result.get("ok") else 400)


@image_gen_bp.route("/setting/images/delete", methods=["POST"])
def image_library_delete():
    auth, error = _auth("library")
    if error:
        return error
    ok = delete_image_asset(request.form.get("identifier"), auth["bot_id"], auth["chat_id"])
    items = list_image_assets(auth["bot_id"], auth["chat_id"], limit=100)
    return render_template(
        "image_library.html",
        token=_token(), auth=auth, items=items,
        message=("已從 Telemini 圖片庫移除，不會刪除 Telegram 原始訊息" if ok else "找不到圖片"),
        expires_at=auth.get("expires_at", 0),
    ), (200 if ok else 404)
