# Prompt Test Lab 子專案

這個資料夾是 Telemini 主遊戲內的獨立調教模組。

設計原則：

- 同一個 Render 伺服器
- 同一個 webhook `/webhook/<bot_id>`
- 透過 `/test` 進入調教模式
- 調教模式不使用主遊戲 `user_config`
- 調教模式不寫主遊戲 `chat_memory`
- 所有資料表都以 `test_` 開頭
- Gemini API Key 儲存在 `test_profiles.gemini_api_key`，和主遊戲 API Key 分開
- 調教模組全部明文保存，不走主遊戲加密，方便直接在 Supabase 查看和修改

## 指令

```text
/test
/test_exit
/test_setting
/test_summary
/test_generate
/test_prompt
/test_key
/test_save_prompt
```

## 資料表

```text
test_profiles
test_sessions
test_memory
test_summaries
test_prompt_versions
```

## 使用流程

1. 在 Telegram 輸入 `/test`。
2. 第一次會要求輸入調教專用 Gemini API Key。
3. key 明文儲存到 `test_profiles.gemini_api_key`。
4. 之後同一聊天室進入 test mode。
5. 看到「已保存調教功能專用 Gemini API Key，現在進入調教模式。」或「已進入 Prompt Test 調教模式。」就可以開始調教。
6. 一般文字都走 Prompt Test Lab，不走主遊戲 Gemini。
7. `/test_setting` 打開網頁調整所有 prompt 欄位。
8. `/test_summary` 摘要最近 300 句測試記憶。
9. `/test_generate` 讓 Gemini 自主改寫 `current_prompt`，把新版 prompt 丟回聊天室，並備份到 `test_prompt_versions`。
10. `/test_save_prompt` 後貼上你的 prompt，系統會保存成 `current_prompt` 並備份到 `test_prompt_versions`。

## 需要的環境變數

沿用主專案：

```text
DATABASE_URL
BASE_URL
SETTING_LINK_SECRET 或 SECRET_KEY
```

不需要 `APP_ENCRYPTION_SECRET` 才能使用 Test Lab。
