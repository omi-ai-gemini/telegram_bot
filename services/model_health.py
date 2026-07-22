import os
from services.database import get_conn

def _admin_ids():
    return [x.strip() for x in str(os.getenv("SERVICE_CENTER_ADMIN_IDS", "")).split(",") if x.strip()]

def notify_model_404_once(model_name: str, detail: str = "") -> None:
    model_name = str(model_name or "").strip()
    if not model_name:
        return
    conn = get_conn()
    claimed = False
    try:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS service_center_model_alerts (
            model_name TEXT PRIMARY KEY,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            detail TEXT DEFAULT '',
            notified_at TIMESTAMP
        )""")
        cur.execute("""INSERT INTO service_center_model_alerts (model_name, detail) VALUES (%s, %s)
            ON CONFLICT (model_name) DO NOTHING RETURNING model_name""", (model_name, str(detail or "")[:500]))
        claimed = bool(cur.fetchone())
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"MODEL 404 ALERT DB ERROR model={model_name}: {exc}", flush=True)
    finally:
        conn.close()
    if not claimed:
        return
    try:
        from service_center.telegram import send_message
        text = f"⚠️ Gemini 模型 404 通知\n模型：{model_name}\n此模型可能已下架或目前 API Key 無權使用。"
        for chat_id in _admin_ids():
            send_message(chat_id, text)
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE service_center_model_alerts SET notified_at=CURRENT_TIMESTAMP WHERE model_name=%s", (model_name,))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        print(f"MODEL 404 ALERT SEND ERROR model={model_name}: {exc}", flush=True)
