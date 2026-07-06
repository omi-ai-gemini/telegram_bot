# Telemini Prompt Test Lab 外帶說明

新增 `test_lab/` 子專案資料夾，主專案只做最小分流。

## 覆蓋檔案

- `main.py`
- `handlers/message_handler.py`

## 新增檔案

- `test_lab/__init__.py`
- `test_lab/db.py`
- `test_lab/gemini.py`
- `test_lab/routes.py`
- `test_lab/service.py`
- `test_lab/telegram.py`
- `test_lab/README.md`
- `templates/test_lab_form.html`
- `docs/TEST_LAB_README.md`

## 功能

- `/test` 進入調教模式。
- 第一次進入會要求輸入調教專用 Gemini API Key。
- 調教模式使用魔改 ID：數字 user_id 會變成 `{user_id}777`。
- 調教模式不寫主遊戲 `user_config`。
- 調教模式不寫主遊戲 `chat_memory`。
- 調教模式只使用 `test_` 開頭資料表。
- `/test_setting` 打開網頁調整 prompt。
- `/test_summary` 摘要最近 300 句測試記憶。
- `/test_generate` 讓 Gemini 自主改寫 `current_prompt`。

## test_ 資料表

- `test_profiles`
- `test_sessions`
- `test_memory`
- `test_summaries`
- `test_prompt_versions`
