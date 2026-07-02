# Project Map

這份檔案由 `tools/project_snapshot.py` 自動產生。

用途：讓 ChatGPT 快速理解目前專案架構，不用每次上傳所有單檔。

## 專案根目錄

```text
C:\Projects\telemini
```

## 主要檔案列表

- `__init__.py`
- `api.py`
- `check_db.py`
- `config.py`
- `handlers\__init__.py`
- `handlers\call_handler.py`
- `handlers\message_handler.py`
- `main.py`
- `requirements.txt`
- `routes\admin.py`
- `routes\setting.py`
- `services\__init__.py`
- `services\bot_router.py`
- `services\call_ai.py`
- `services\character.py`
- `services\chat_persona.py`
- `services\commands.py`
- `services\database.py`
- `services\gemini_service.py`
- `services\memory.py`
- `services\reply_style.py`
- `services\style.py`
- `services\telegram_service.py`
- `services\user_router.py`
- `templates\character_form.html`
- `templates\chat_persona_form.html`
- `templates\developer.html`
- `templates\index.html`
- `templates\login.html`
- `templates\manual.html`
- `templates\reply_style_form.html`
- `test_db.py`
- `tools\project_snapshot.py`
- `模式-使用說明.txt`

## Python 路由總覽

### `api.py`
- `/api/bot` → `add_bot`
- `/api/bot` → `get_bots`
- `/api/user` → `add_user`
- `/api/user` → `get_users`

### `main.py`
- `/webhook/<bot_id>` → `webhook`
- `/` → `home`

### `routes\admin.py`
- `/admin` → `admin`
- `/admin/login` → `admin_login`
- `/admin/login` → `admin_login_post`
- `/admin/manual` → `admin_manual`
- `/admin/manual/add_bot` → `add_bot_route`
- `/admin/manual/add_key` → `add_key_route`
- `/admin/login/developer` → `admin_login_developer`

### `routes\setting.py`
- `/setting/persona` → `persona_setting_page`
- `/setting/character` → `character_setting_page`
- `/setting/reply_style` → `reply_style_setting_page`
- `/setting/reply_style/save` → `save_reply_style_setting`
- `/setting/chat_persona/save` → `save_chat_persona_setting`
- `/setting/character/save` → `save_character_setting`

## Python 函式總覽

### `api.py`
- `add_bot()`
- `get_bots()`
- `add_user()`
- `get_users()`

### `handlers\call_handler.py`
- `handle_ui()`

### `handlers\message_handler.py`
- `handle_message()`

### `main.py`
- `init_once()`
- `webhook()`
- `home()`

### `routes\admin.py`
- `admin()`
- `admin_login()`
- `admin_login_post()`
- `admin_manual()`
- `add_bot_route()`
- `add_key_route()`
- `admin_login_developer()`

### `routes\setting.py`
- `persona_setting_page()`
- `character_setting_page()`
- `reply_style_setting_page()`
- `save_reply_style_setting()`
- `save_chat_persona_setting()`
- `save_character_setting()`

### `services\bot_router.py`
- `_text_id()`
- `get_bot_token()`
- `bot_exists()`
- `clear_bot_token_cache()`

### `services\call_ai.py`
- `run_ai()`

### `services\character.py`
- `_text_id()`
- `get_character_mode()`
- `update_character_mode()`
- `get_character_settings()`
- `update_character_settings()`
- `delete_character_settings()`

### `services\chat_persona.py`
- `_text_id()`
- `has_chat_persona_settings()`
- `get_chat_persona_settings()`
- `update_chat_persona_settings()`
- `delete_chat_persona_settings()`

### `services\commands.py`
- `_telegram_post()`
- `_build_persona_setting_url()`
- `_build_reply_style_url()`
- `_send_or_edit()`
- `_send_new_message()`
- `send_setting_menu()`
- `send_character_menu()`
- `send_reply_style_menu()`
- `send_mode_menu()`
- `send_memory_menu()`
- `send_clear_memory_confirm_message()`
- `send_delete_character_confirm_message()`
- `send_delete_reply_style_confirm_message()`

### `services\database.py`
- `get_conn()`
- `get_db_connection_stats()`
- `save_bot()`
- `update_gemini_key()`
- `init_db()`
- `__init__()`
- `close()`
- `__getattr__()`
- `__enter__()`
- `__exit__()`

### `services\gemini_service.py`
- `ask_gemini()`
- `summarize_memory()`

### `services\memory.py`
- `_text_id()`
- `_get_scope()`
- `delete_current_memory()`
- `delete_character_memory()`
- `update_emotion()`
- `get_emotion()`
- `detect_emotion()`
- `is_memory_command()`
- `extract_memory_content()`
- `add_fact()`
- `get_facts()`
- `add_chat()`
- `get_chat()`
- `get_recent_chat()`

### `services\reply_style.py`
- `_text_id()`
- `normalize_style_type()`
- `_get_legacy_reply_style()`
- `get_reply_style_settings()`
- `update_reply_style_settings()`
- `delete_reply_style_settings()`

### `services\style.py`
- `_has_chat_persona()`
- `_build_chat_persona_text()`
- `_build_character_text()`
- `_build_reply_style_text()`
- `_build_facts_text()`
- `build_prompt()`

### `services\telegram_service.py`
- `send_message()`
- `answer_callback_query()`
- `delete_message()`

### `services\user_router.py`
- `_text_id()`
- `get_gemini_key()`
- `user_has_key()`

### `tools\project_snapshot.py`
- `should_ignore()`
- `get_project_files()`
- `generate_tree()`
- `analyze_python_file()`
- `extract_route_from_decorator()`
- `summarize_file()`
- `generate_project_map()`
- `main()`
