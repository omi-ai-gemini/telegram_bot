import requests
from config import TELEGRAM_API_BASE
from services.telegram_service import get_bot_token

# =========================
# Telegram 發送訊息
# =========================
def send_message(bot_id, chat_id, text):

    token = get_bot_token(bot_id)

    if not token:
        print("X token not found")
        return
    
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )