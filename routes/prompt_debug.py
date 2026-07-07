import difflib

from flask import Blueprint, render_template, request

from services.prompt_debug import (
    get_prompt_debug_log,
    list_prompt_debug_logs,
    verify_prompt_debug_token,
)


prompt_debug_bp = Blueprint("prompt_debug", __name__)


def _auth_from_request():
    token = request.args.get("token", "")
    auth = verify_prompt_debug_token(token)
    if not auth.get("ok"):
        return auth, token, ("Prompt Debug 連結已失效或驗證失敗", 403)
    return auth, token, None


@prompt_debug_bp.route("/prompt_debug", methods=["GET"])
def prompt_debug_list_page():
    auth, token, error = _auth_from_request()
    if error:
        return error

    items = list_prompt_debug_logs(
        bot_id=auth["bot_id"],
        chat_id=auth["chat_id"],
        user_id=auth["user_id"],
        limit=30,
    )

    return render_template(
        "prompt_debug_list.html",
        token=token,
        auth=auth,
        items=items,
    )


@prompt_debug_bp.route("/prompt_debug/<int:log_id>", methods=["GET"])
def prompt_debug_detail_page(log_id):
    auth, token, error = _auth_from_request()
    if error:
        return error

    item = get_prompt_debug_log(
        log_id=log_id,
        bot_id=auth["bot_id"],
        chat_id=auth["chat_id"],
        user_id=auth["user_id"],
    )

    if not item:
        return "找不到這筆 Prompt Debug 紀錄", 404

    return render_template(
        "prompt_debug_detail.html",
        token=token,
        auth=auth,
        item=item,
    )


@prompt_debug_bp.route("/prompt_debug/compare", methods=["GET"])
def prompt_debug_compare_page():
    auth, token, error = _auth_from_request()
    if error:
        return error

    left_id = request.args.get("left_id")
    right_id = request.args.get("right_id")

    items = list_prompt_debug_logs(
        bot_id=auth["bot_id"],
        chat_id=auth["chat_id"],
        user_id=auth["user_id"],
        limit=30,
    )

    if not left_id or not right_id:
        if len(items) >= 2:
            # 預設比對最新兩筆：右邊是最新，左邊是上一筆。
            latest_id = items[0]["id"]
            previous_id = items[1]["id"]

            if right_id and not left_id:
                left_id = latest_id if str(right_id) != str(latest_id) else previous_id
            elif left_id and not right_id:
                right_id = latest_id if str(left_id) != str(latest_id) else previous_id
            else:
                right_id = latest_id
                left_id = previous_id

    left = get_prompt_debug_log(left_id, auth["bot_id"], auth["chat_id"], user_id=auth["user_id"]) if left_id else None
    right = get_prompt_debug_log(right_id, auth["bot_id"], auth["chat_id"], user_id=auth["user_id"]) if right_id else None

    diff_table = ""
    if left and right:
        differ = difflib.HtmlDiff(tabsize=2, wrapcolumn=120)
        diff_table = differ.make_table(
            left.get("prompt_text", "").splitlines(),
            right.get("prompt_text", "").splitlines(),
            fromdesc=f"#{left.get('id')} {left.get('source')} / {left.get('status')}",
            todesc=f"#{right.get('id')} {right.get('source')} / {right.get('status')}",
            context=True,
            numlines=5,
        )

    return render_template(
        "prompt_debug_compare.html",
        token=token,
        auth=auth,
        items=items,
        left=left,
        right=right,
        diff_table=diff_table,
    )
