# Service Center Stage 2

## 修改目標

這包只做服務中心功能，不動主遊戲 AI 回覆流程。

更新項目：

1. 公告事項
   - 新增 `service_center_announcements` table。
   - 點「📢 公告事項」後，從最新公告開始往下顯示。
   - 支援分頁：上一頁 / 下一頁。
   - 管理員可用 `/公告 標題\n公告內容` 新增公告。

2. Telemini Wifi
   - 服務中心內新增「開始連線新 Bot」。
   - 使用者貼 BotFather token 後：
     - 自動呼叫 Telegram `getMe` 驗證 token。
     - 用 bot username 當 `bot_id`。
     - 寫入既有 `bot_config`。
     - 自動設定 webhook 到 `BASE_URL/webhook/<bot_id>`。
     - 清除 bot token 快取。
   - 含 token 的使用者訊息會自動刪除。

3. Gemini API
   - 服務中心內新增「新增 / 更改 Gemini API」。
   - 使用者貼 Gemini API Key 後：
     - 寫入既有 `user_config`。
     - 清除 key 快取。
   - 含 API Key 的使用者訊息會自動刪除。

4. 操作說明
   - 保留操作說明文字提示。
   - 新增分類按鈕：
     - 遊戲模式
     - 自訂風格
     - 聊天與劇場內容設定
     - 記憶操作
     - 開場白

## 修改檔案

```text
main.py
service_center/db.py
service_center/handler.py
service_center/telegram.py
docs/SERVICE_CENTER_STAGE2_README.md
```

## 需要環境變數

```text
BASE_URL=https://你的-render網址
SERVICE_CENTER_BOT_ID=service_center
SERVICE_CENTER_BOT_TOKEN=服務中心bot token
SERVICE_CENTER_ADMIN_IDS=你的Telegram數字ID
```

## 管理員新增公告

在服務中心 bot 私訊：

```text
/公告 系統更新
這裡是公告內容
可以換行
```

或：

```text
/announce System Update
Announcement body
```

## 測試

```bash
python -m py_compile main.py service_center/db.py service_center/handler.py service_center/telegram.py services/database.py
```
