# Telemini 設定頁簽章網址鎖

## 必填環境變數

Render Environment Variables 新增：

```text
SETTING_LINK_SECRET=一串長隨機字串
```

可用本機產生：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 規則

- 設定頁連結有效 15 分鐘。
- 頁面會顯示「請在時效內按儲存」與倒數時間。
- 剩 3 分鐘時會改成提醒「連結即將失效，請盡快儲存」。
- 過期後前端會鎖住儲存按鈕。
- 後端也會重新驗證 token；過期或被改過都不會寫入 DB。
- 群組設定頁目前保留延伸，不開放直接進入或儲存。

## 會鎖的路由

```text
GET  /setting/persona
GET  /setting/character
GET  /setting/reply_style
GET  /setting/important_memory
GET  /setting/important_memory/list

POST /setting/chat_persona/save
POST /setting/character/save
POST /setting/reply_style/save
POST /setting/important_memory/save
POST /setting/important_memory/update
POST /setting/important_memory/delete
```

## 不會影響既有資料

這個更新只改「開啟 / 儲存設定頁」的權限驗證，不改既有資料內容，不需要搬資料、不需要重建資料表。
