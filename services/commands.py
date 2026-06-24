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
                        "text": "🤖 AI設定",
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
    