# 服務中心 bot token 已改由環境變數 SERVICE_CENTER_BOT_TOKEN 管理。
# 這個檔案刻意不建立任何資料表，保留空檔是為了覆蓋舊 stage1 補丁可能留下的 service_center/db.py。


def init_service_center_db():
    """相容舊匯入用的 no-op；不建立 table。"""
    return None
