from flask import Blueprint, request
from html import escape

setting_bp = Blueprint("setting", __name__)


# =========================
# 劇本設定表單頁入口
# =========================
@setting_bp.route("/setting/character", methods=["GET"])
def character_setting_page():

    bot_id = request.args.get("bot_id", "")
    chat_id = request.args.get("chat_id", "")
    user_id = request.args.get("user_id", "")

    # 防止使用者輸入奇怪字元影響 HTML
    bot_id_safe = escape(bot_id)
    chat_id_safe = escape(chat_id)
    user_id_safe = escape(user_id)

    return f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>劇本設定</title>
        <style>
            body {{
                margin: 0;
                padding: 24px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: #0f172a;
                color: #ffffff;
            }}

            .card {{
                max-width: 520px;
                margin: 0 auto;
                padding: 24px;
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
            }}

            h1 {{
                font-size: 24px;
                margin-bottom: 12px;
            }}

            p {{
                line-height: 1.7;
                color: rgba(255, 255, 255, 0.82);
            }}

            .debug {{
                margin-top: 20px;
                padding: 14px;
                border-radius: 12px;
                background: rgba(0, 0, 0, 0.25);
                font-size: 14px;
                line-height: 1.7;
                color: rgba(255, 255, 255, 0.78);
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📖 劇本設定</h1>
            <p>這裡是 Telegram 劇本設定表單入口。</p>
            <p>目前 route 已接通，下一步會把這裡改成正式輸入表單。</p>

            <div class="debug">
                bot_id：{bot_id_safe}<br>
                chat_id：{chat_id_safe}<br>
                user_id：{user_id_safe}
            </div>
        </div>
    </body>
    </html>
    """