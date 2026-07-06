# Prompt Test Lab 子專案

這個資料夾是 Telemini 主遊戲內的獨立調教模組。

設計原則：

- 同一個 Render 伺服器
- 同一個 webhook `/webhook/<bot_id>`
- 透過 `/test` 進入調教模式
- 調教模式不使用主遊戲 `user_config`
- 調教模式不寫主遊戲 `chat_memory`
- 所有資料表都以 `test_` 開頭
- Gemini API Key 儲存在 `test_profiles`，和主遊戲 API Key 分開

## 指令

```text
/test
/test_exit
/test_setting
/test_summary
/test_generate
/test_prompt
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
3. key 儲存到 `test_profiles.gemini_api_key`。
4. 之後同一聊天室進入 test mode。
5. 一般文字都走 Prompt Test Lab，不走主遊戲 Gemini。
6. `/test_setting` 打開網頁調整所有 prompt 欄位。
7. `/test_summary` 摘要最近 300 句測試記憶。
8. `/test_generate` 讓 Gemini 自主改寫 `current_prompt`。

## 需要的環境變數

沿用主專案：

```text
DATABASE_URL
BASE_URL
SETTING_LINK_SECRET 或 SECRET_KEY
APP_ENCRYPTION_SECRET
```

`APP_ENCRYPTION_SECRET` 用於加密 `test_profiles.gemini_api_key`。
