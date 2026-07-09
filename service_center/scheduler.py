import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from service_center.db import (
    SCHEDULER_STATE_KEY,
    claim_announcement_delivery,
    get_scheduler_state,
    list_pushable_announcements,
    list_service_center_subscribers,
    mark_announcement_delivery_result,
    mark_announcement_pushed,
    mark_service_center_subscriber_inactive,
    set_scheduler_state,
)
from service_center.telegram import send_message


TAIPEI_TZ = ZoneInfo("Asia/Taipei")
PUSH_HOUR = 17
PUSH_MINUTE = 0
CHECK_INTERVAL_SECONDS = 60
_STARTED = False
_LOCK = threading.Lock()


def _text_id(value):
    return str(value or "").strip()


def _today_key(now=None):
    now = now or datetime.now(TAIPEI_TZ)
    return now.strftime("%Y-%m-%d")


def _is_push_time(now=None):
    now = now or datetime.now(TAIPEI_TZ)
    return (now.hour, now.minute) >= (PUSH_HOUR, PUSH_MINUTE)


def _format_announcement_push(item):
    label = _text_id(item.get("label")) or "公告"
    title = _text_id(item.get("title")) or "更新公告"
    body = _text_id(item.get("body"))

    return f"📢 [{label}] {title}\n\n{body}"


def push_pending_announcements_once(reason="manual"):
    """推播尚未送到各 chat 的公告。delivery table 會擋掉重複推播。"""
    announcements = list_pushable_announcements(limit=20)
    subscribers = list_service_center_subscribers(limit=5000)

    if not announcements:
        print(
            f"SERVICE CENTER ANNOUNCEMENT PUSH SKIP reason={reason} announcements=0",
            flush=True,
        )
        return {"sent": 0, "failed": 0, "claimed": 0}

    if not subscribers:
        for announcement in announcements:
            mark_announcement_pushed(announcement.get("id"))
        print(
            f"SERVICE CENTER ANNOUNCEMENT PUSH NO SUBSCRIBERS reason={reason} "
            f"announcements={len(announcements)} marked_pushed={len(announcements)}",
            flush=True,
        )
        return {"sent": 0, "failed": 0, "claimed": 0}

    sent = 0
    failed = 0
    claimed = 0

    for announcement in announcements:
        announcement_id = announcement.get("id")
        text = _format_announcement_push(announcement)

        for subscriber in subscribers:
            chat_id = subscriber.get("chat_id")
            delivery_id = claim_announcement_delivery(announcement_id, chat_id)

            if not delivery_id:
                continue

            claimed += 1

            result = send_message(chat_id=chat_id, text=text)
            ok = bool(result and result.get("ok", True))

            if ok:
                sent += 1
                mark_announcement_delivery_result(delivery_id, ok=True)
            else:
                failed += 1
                mark_announcement_delivery_result(delivery_id, ok=False, error_text="telegram_send_failed")
                # 使用者封鎖 bot 或 chat 不可達時，先暫停後續主動推播。
                mark_service_center_subscriber_inactive(chat_id)

        # 這則公告的當日排程已處理完，之後不再主動推給新 subscriber。
        mark_announcement_pushed(announcement_id)

    print(
        f"SERVICE CENTER ANNOUNCEMENT PUSH DONE reason={reason} "
        f"claimed={claimed} sent={sent} failed={failed}",
        flush=True,
    )
    return {"sent": sent, "failed": failed, "claimed": claimed}


def _scheduler_loop():
    print("SERVICE CENTER ANNOUNCEMENT SCHEDULER START", flush=True)

    while True:
        try:
            now = datetime.now(TAIPEI_TZ)
            today = _today_key(now)
            last_push_date = get_scheduler_state(SCHEDULER_STATE_KEY)

            if _is_push_time(now) and last_push_date != today:
                push_pending_announcements_once(reason=f"daily_17_taipei_{today}")
                set_scheduler_state(SCHEDULER_STATE_KEY, today)

        except Exception as exc:
            print("SERVICE CENTER ANNOUNCEMENT SCHEDULER ERROR:", exc, flush=True)

        time.sleep(CHECK_INTERVAL_SECONDS)


def start_service_center_announcement_scheduler():
    """啟動公告推播排程。每個 process 只啟動一次；實際重複推播由 DB unique delivery 擋住。"""
    global _STARTED

    with _LOCK:
        if _STARTED:
            return False

        _STARTED = True
        thread = threading.Thread(target=_scheduler_loop, daemon=True)
        thread.start()
        return True
