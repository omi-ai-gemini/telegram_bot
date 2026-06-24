import requests

def send_setting_menu(bot_token, chat_id):

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": "⚙️ 設定中心",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "👤 人物設定",
                        "callback_data": "ai_setting"
                    }
                ],
                [
                    {
                        "text": "🧠 記憶設定",
                        "callback_data": "memory_setting"
                    }
                ],
                [
                    {
                        "text": "🔑 API設定",
                        "callback_data": "api_setting"
                    }
                ]
            ]
        }
    }

    requests.post(url, json=payload)

def send_character_menu(bot_token, chat_id):

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": "👤 人物設定",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "🎭 模式",
                        "callback_data": "character_mode"
                    }
                ],
                [
                    {
                        "text": "📝 角色設定",
                        "callback_data": "edit_role"
                    }
                ],
                [
                    {
                        "text": "👤 個人設定",
                        "callback_data": "edit_user"
                    }
                ],
                [
                    {
                        "text": "💬 角色開場白",
                        "callback_data": "edit_opening"
                    }
                ],
                [
                    {
                        "text": "🗑️ 刪除所有設定",
                        "callback_data": "delete_character"
                    }
                ],
                [
                    {
                        "text": "⬅️ 返回",
                        "callback_data": "back_setting"
                    }
                ]
            ]
        }
    }

    requests.post(url, json=payload)