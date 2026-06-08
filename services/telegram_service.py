import requests
from config import TELEGRAM_API

# =========================
# Telegram 發送訊息
# =========================
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )