# Telemini Prompt Test Lab 外帶說明

新增 `test_lab/` 子專案資料夾，主專案只做最小分流。

## 覆蓋檔案

- `main.py`
- `handlers/message_handler.py`

## 新增 / 更新檔案

- `test_lab/__init__.py`
- `test_lab/db.py`
- `test_lab/gemini.py`
- `test_lab/routes.py`
- `test_lab/service.py`
- `test_lab/telegram.py`
- `test_lab/README.md`
- `test_lab/templates/test_lab_form.html`
- `docs/TEST_LAB_README.md`

## 功能

- `/test` 進入調教模式。
- 第一次進入會要求輸入調教專用 Gemini API Key。
- 調教用 Gemini API Key 明文存到 `test_profiles.gemini_api_key`，不走主遊戲加密。
- 調教模式使用魔改 ID：數字 user_id 會變成 `{user_id}777`。
- 調教模式不寫主遊戲 `user_config`。
- 調教模式不寫主遊戲 `chat_memory`。
- 調教模式只使用 `test_` 開頭資料表。
- `/test_setting` 打開網頁調整 prompt。
- `/test_summary` 摘要最近 300 句測試記憶。
- `/test_generate` 讓 Gemini 自主改寫 `current_prompt`，直接把新版 prompt 丟回聊天室，並寫入 `test_prompt_versions` 備份。
- `/test_save_prompt` 進入手動保存 prompt 狀態，下一則訊息會保存到 `current_prompt` 並寫入 `test_prompt_versions` 備份。
- `/test_save_prompt 你的prompt` 可用單行方式直接保存。
- `/test_key` 可重新輸入調教專用 Gemini API Key。
- `/test_prompt` 查看目前 `current_prompt`。

## test_ 資料表

- `test_profiles`
- `test_sessions`
- `test_memory`
- `test_summaries`
- `test_prompt_versions`

## 明文保存

調教模組是開發者測試工具，所有 test_ 表資料都明文保存，方便直接在 Supabase 查看、修改與備份。
