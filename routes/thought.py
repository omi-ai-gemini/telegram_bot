from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template

from services.ai_actions import get_ai_thought_summary_by_token


thought_bp = Blueprint("thought", __name__)
TAIPEI_TIMEZONE = ZoneInfo("Asia/Taipei")


def _format_time(ts):
    if not ts:
        return ""

    try:
        return datetime.fromtimestamp(float(ts), TAIPEI_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


@thought_bp.route("/thought/<token>", methods=["GET"])
def thought_page(token):
    """
    單筆 Gemini 推理摘要查看頁。

    只從 Render 記憶體快取讀取：
    - 不查 DB
    - 不寫 DB
    - 不列出其他推理摘要
    - 快取不存在或過期就顯示過期
    """
    item = get_ai_thought_summary_by_token(token)

    if not item:
        return render_template(
            "thought_view.html",
            expired=True,
            thought_text="",
            created_at="",
            expires_at="",
        )

    return render_template(
        "thought_view.html",
        expired=False,
        thought_text=item.get("text", ""),
        created_at=_format_time(item.get("created_at")),
        expires_at=_format_time(item.get("expires_at")),
    )
