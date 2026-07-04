from datetime import datetime
from zoneinfo import ZoneInfo

TAIPEI_TIMEZONE = "Asia/Taipei"
WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _period_name(hour: int) -> str:
    if 5 <= hour <= 10:
        return "早上"
    if 11 <= hour <= 13:
        return "中午"
    if 14 <= hour <= 17:
        return "下午"
    if 18 <= hour <= 21:
        return "晚上"
    return "深夜"


def get_current_time_context() -> dict:
    """
    取得目前台灣時間。
    這個資料不寫 DB，每次 Gemini 回覆前即時計算。
    """
    now = datetime.now(ZoneInfo(TAIPEI_TIMEZONE))

    return {
        "timezone": TAIPEI_TIMEZONE,
        "date": now.strftime("%Y年%m月%d日"),
        "weekday": WEEKDAY_ZH[now.weekday()],
        "time": now.strftime("%H:%M"),
        "period": _period_name(now.hour),
        "iso": now.isoformat(timespec="seconds"),
        "timestamp": int(now.timestamp()),
    }


def build_time_context_text(time_context=None) -> str:
    """
    組成 prompt 使用的現實時間資訊。
    """
    data = time_context or get_current_time_context()

    return (
        f"時區：{data.get('timezone', TAIPEI_TIMEZONE)}（台灣時間）\n"
        f"日期：{data.get('date', '')}\n"
        f"星期：{data.get('weekday', '')}\n"
        f"時間：{data.get('time', '')}\n"
        f"時段：{data.get('period', '')}"
    )
