# Telemini 環境變數主密鑰加密版

這版改成用 Render Environment Variables 裡的 `APP_ENCRYPTION_SECRET` 做加解密。

## 目標

- 原本 table 照用，不再把短期記憶搬到 `encrypted_settings`。
- 寫入 Supabase 前加密。
- 從 Supabase 讀出後自動解密給原本流程使用。
- 不需要使用者保存資料庫密碼。
- 不需要 `/解鎖`。
- Render log 不印 prompt / Gemini response 明文。

## 必填環境變數

在本機或 Render 產生一串密鑰：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

到 Render 設定：

```text
APP_ENCRYPTION_SECRET=剛剛產生的一整串
```

不能放進 GitHub。

## 會加密的欄位

```text
chat_memory.text
facts_memory.fact
character_settings.ai_name
character_settings.ai_gender
character_settings.ai_appearance
character_settings.story_background
character_settings.ai_opening
character_settings.user_gender
character_settings.user_appearance
character_settings.user_other_settings
chat_persona_settings.persona_name
chat_persona_settings.persona_gender
chat_persona_settings.persona_background
reply_style_settings.reply_style
```

## Supabase 會看到什麼

會看到類似：

```text
ENCv1:{"v":1,"n":"...","c":"..."}
```

程式讀取時會自動解密，所以 Gemini 還是拿到正常文字。

## 舊明文資料

部署後「新寫入」會是密文。

舊資料不會自動消失。要把舊資料轉成密文，在 Render Shell 或本機有 `DATABASE_URL` / `APP_ENCRYPTION_SECRET` 的環境執行：

```bash
python tools/encrypt_existing_plaintext.py
```

先測試可用：

```bash
python tools/encrypt_existing_plaintext.py --dry-run
```

## Log 注意

`services/gemini_service.py` 已移除：

```python
print("DEBUG prompt preview:", prompt[:1200])
print("gemini response:", response.text)
```

因為 prompt 裡會有解密後的明文。

## 安全邊界

可以防：

- 直接在 Supabase Dashboard 看資料。
- 匯出 DB 後直接看內容。

不能防：

- 有 Render 環境變數權限的人。
- 可以修改程式碼的人。
- 你自己把 prompt / response 印進 log。
