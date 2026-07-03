# Telemini 隱私管理權限 / 資料庫密碼自動補發包

## 這包做了什麼

新增：

- `services/crypto_box.py`
- `services/encrypted_store.py`
- `services/privacy_access.py`
- `docs/PRIVACY_ACCESS_README.md`

覆蓋：

- `services/database.py`
- `services/telegram_service.py`
- `handlers/message_handler.py`
- `requirements.txt`

## 使用者取得密碼流程

每次文字訊息進入 `handle_message()` 時，會先呼叫：

```python
ensure_privacy_password_issued(user_id, bot_id, chat_id)
```

但它不是每次都查 DB：

1. 同一個 Render process 內，已發放者會進 `_ISSUED_CACHE`。
2. 已發放後後續訊息直接略過。
3. Render 重啟後，第一次會查 DB，查到已發放後又進快取。

## 私聊

使用者下一次私聊 bot，只要還沒拿過，就會自動收到：

```text
資料庫新增隱私管理權限
個別資料庫密碼：
XXXXXXXXXXXXXX

妥善保存密碼，遺失就無法後台修改。
隱私保護項目：記憶資料、劇本資料、風格資料、人物設定資料、後續納入隱私保護的資料

注意：系統不會保存這組密碼明文，之後也不會再次顯示。
```

## 群組

群組內不公開傳密碼。

流程：

1. 使用者在群組傳訊息。
2. 系統嘗試私訊該使用者。
3. 如果私訊成功，密碼送到私聊。
4. 如果私訊失敗，群組只提示使用者先去私訊 bot。

## DB 狀態表

```sql
privacy_access
- user_id
- bot_id
- unlock_code_issued
- delivery_status
- issued_chat_id
- issued_at
- created_at
- updated_at
```

注意：DB 不保存明文密碼，只記錄是否已發放。

## 加密資料表

```sql
encrypted_settings
- user_id
- bot_id
- chat_id
- data_type
- record_key
- encrypted_payload
```

真正內容包成 JSON 後加密放進 `encrypted_payload`。

## 下一步接入

目前這包已經完成：

- 自動補發資料庫密碼
- 已取得狀態記錄
- 快取避免每次查 DB
- AES-GCM JSON payload 加密底層

接下來要把記憶、劇本、風格資料改成加密時，使用：

```python
save_encrypted_payload(...)
get_encrypted_payload(...)
```
