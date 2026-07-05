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
- `docs\AI_MESSAGE_ACTIONS_README.md`
- `docs\ENV_ENCRYPTION_README.md`
- `docs\PRIVACY_ACCESS_README.md`
- `docs\PRIVACY_SYNC_README.md`
- `docs\REPLY_NONBLOCKING_BUTTONS_README.md`
- `docs\REPLY_RECOVERY_README.md`
- `docs\REPLY_RECOVERY_SECRET_FIX_README.md`
- `docs\SETTING_LINK_AUTH_README.md`
- `docs\SMALL_UPDATE_MEMORY_VIEW_README.md`
- `docs\THOUGHT_WEB_VIEW_README.md`
- `handlers\__init__.py`
- `handlers\call_handler.py`
- `handlers\message_handler.py`
- `main.py`
- `requirements.txt`
- `routes\admin.py`
- `routes\setting.py`
- `routes\thought.py`
- `services\__init__.py`
- `services\ai_actions.py`
- `services\bot_router.py`
- `services\call_ai.py`
- `services\character.py`
- `services\chat_persona.py`
- `services\commands.py`
- `services\crypto_box.py`
- `services\crypto_env.py`
- `services\database.py`
- `services\encrypted_store.py`
- `services\gemini_service.py`
- `services\memory.py`
- `services\memory_summary.py`
- `services\memory_view.py`
- `services\privacy_access.py`
- `services\privacy_migration.py`
- `services\privacy_session.py`
- `services\reply_style.py`
- `services\setting_auth.py`
- `services\setting_sessions.py`
- `services\style.py`
- `services\telegram_service.py`
- `services\time_context.py`
- `services\user_notice.py`
- `services\user_router.py`
- `telemini\services\call_ai.py`
- `telemini\services\database.py`
- `telemini\services\memory.py`
- `telemini\services\style.py`
- `telemini\templates\important_memory_form.html`
- `templates\character_form.html`
- `templates\chat_persona_form.html`
- `templates\developer.html`
- `templates\important_memory_form.html`
- `templates\index.html`
- `templates\login.html`
- `templates\manual.html`
- `templates\reply_style_form.html`
- `templates\thought_view.html`
- `test_db.py`
- `tools\encrypt_existing_plaintext.py`
- `tools\project_snapshot.py`
- `tools\python.txt`
- `外帶說明.txt`
- `模式-使用說明.txt`
- `開場-更新說明.txt`

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
- `/setting/important_memory` → `important_memory_setting_page`
- `/setting/important_memory/save` → `save_important_memory_setting`
- `/setting/important_memory/list` → `list_important_memory_setting`
- `/setting/important_memory/update` → `update_important_memory_setting`
- `/setting/important_memory/delete` → `delete_important_memory_setting`
- `/setting/persona` → `persona_setting_page`
- `/setting/character` → `character_setting_page`
- `/setting/reply_style` → `reply_style_setting_page`
- `/setting/reply_style/save` → `save_reply_style_setting`
- `/setting/chat_persona/save` → `save_chat_persona_setting`
- `/setting/character/save` → `save_character_setting`

### `routes\thought.py`
- `/thought/<token>` → `thought_page`

## Python 函式總覽

### `api.py`
- `add_bot()`
- `get_bots()`
- `add_user()`
- `get_users()`

### `handlers\call_handler.py`
- `_setting_fallback_text()`
- `_send_script_opening()`
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
- `_auth_or_page_error()`
- `_auth_or_json_error()`
- `_is_group_chat()`
- `_token_from_request()`
- `important_memory_setting_page()`
- `save_important_memory_setting()`
- `list_important_memory_setting()`
- `update_important_memory_setting()`
- `delete_important_memory_setting()`
- `persona_setting_page()`
- `character_setting_page()`
- `reply_style_setting_page()`
- `save_reply_style_setting()`
- `save_chat_persona_setting()`
- `save_character_setting()`

### `routes\thought.py`
- `_format_time()`
- `thought_page()`

### `services\ai_actions.py`
- `_text_id()`
- `_is_group_chat()`
- `_should_show_ai_buttons_for_mode()`
- `_should_show_ai_buttons()`
- `_hidden_reply_markup()`
- `_purge_expired_thought_cache()`
- `_get_or_create_ai_thought_token()`
- `get_ai_thought_url()`
- `build_ai_action_keyboard()`
- `_get_latest_ai_action_id()`
- `_create_latest_hidden_action_from_memory()`
- `send_hidden_ai_action_menu()`
- `cache_ai_thought_summary()`
- `clear_ai_thought_summary()`
- `get_ai_thought_summary_by_token()`
- `_split_gemini_result()`
- `create_ai_message_action()`
- `update_action_telegram_message_id()`
- `get_ai_message_action()`
- `create_pending_edit()`
- `pop_active_pending_edit()`
- `_extract_telegram_message_id()`
- `start_edit_ai_message()`
- `process_pending_edit_message()`
- `_load_generation_context()`
- `_generate_reply()`
- `regenerate_ai_message()`
- `continue_ai_message()`
- `reply_ai_message()`
- `run_reply_ai_message_in_thread()`
- `run_regenerate_in_thread()`
- `run_continue_in_thread()`

### `services\bot_router.py`
- `_text_id()`
- `get_bot_token()`
- `bot_exists()`
- `clear_bot_token_cache()`

### `services\call_ai.py`
- `_is_group_chat()`
- `_extract_telegram_message_id()`
- `_send_ai_message_with_retry()`
- `_get_generation_settings()`
- `_attach_reply_buttons_in_background()`
- `_send_generated_reply()`
- `run_ai()`
- `run_reply_recovery()`
- `worker()`

### `services\character.py`
- `_text_id()`
- `_clean_text()`
- `_decrypt_field()`
- `_encrypt_field()`
- `build_script_hash()`
- `get_character_mode()`
- `update_character_mode()`
- `get_character_settings()`
- `get_script_opening_status()`
- `mark_script_opening_sent()`
- `update_character_settings()`
- `delete_character_settings()`

### `services\chat_persona.py`
- `_text_id()`
- `_decrypt_field()`
- `_encrypt_field()`
- `has_chat_persona_settings()`
- `get_chat_persona_settings()`
- `update_chat_persona_settings()`
- `delete_chat_persona_settings()`

### `services\commands.py`
- `_telegram_post()`
- `_build_persona_setting_url()`
- `_build_important_memory_url()`
- `_build_reply_style_url()`
- `_send_or_edit()`
- `_send_new_message()`
- `_extract_message_id()`
- `send_setting_menu()`
- `send_character_menu()`
- `send_reply_style_menu()`
- `send_start_script_confirm_menu()`
- `send_mode_menu()`
- `send_memory_menu()`
- `send_clear_memory_confirm_message()`
- `send_delete_character_confirm_message()`
- `send_delete_reply_style_confirm_message()`

### `services\crypto_box.py`
- `generate_unlock_code()`
- `build_aad()`
- `_b64_encode()`
- `_b64_decode()`
- `derive_key()`
- `encrypt_payload()`
- `decrypt_payload()`

### `services\crypto_env.py`
- `_get_master_key()`
- `_b64e()`
- `_b64d()`
- `is_encrypted()`
- `encrypt_text()`
- `decrypt_text()`
- `aad_for()`

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

### `services\encrypted_store.py`
- `create_user_unlock_code()`
- `save_encrypted_payload()`
- `get_encrypted_payload()`
- `delete_encrypted_payload()`
- `list_encrypted_metadata()`

### `services\gemini_service.py`
- `_with_structured_reply_instructions()`
- `_strip_code_fence()`
- `_extract_json_object_text()`
- `_parse_structured_reply()`
- `_build_gemini_config()`
- `_enum_name()`
- `_read_attr()`
- `_extract_finish_reason()`
- `get_gemini_block_reason()`
- `debug_gemini_response()`
- `_safe_response_text()`
- `_extract_answer_and_thoughts()`
- `_meta_result()`
- `ask_gemini()`
- `summarize_memory()`

### `services\memory.py`
- `_text_id()`
- `_get_scope()`
- `_decrypt_safe()`
- `delete_current_memory()`
- `delete_character_memory()`
- `update_emotion()`
- `get_emotion()`
- `detect_emotion()`
- `is_memory_command()`
- `extract_memory_content()`
- `_normalize_fact_for_hash()`
- `_fact_hash()`
- `add_fact()`
- `add_important_fact()`
- `get_facts()`
- `_user_filter_sql()`
- `list_important_facts()`
- `update_important_fact()`
- `delete_important_fact()`
- `add_chat()`
- `update_chat_text()`
- `get_chat_memory_item()`
- `get_chat_until()`
- `get_chat()`
- `list_recent_chat_memory()`
- `delete_chat_memory_item()`
- `get_recent_chat()`

### `services\memory_summary.py`
- `_notify_summary_blocked()`
- `_is_summary_blocked()`
- `_text_id()`
- `_get_scope()`
- `_decrypt_safe()`
- `_fetch_unsummarized_rows()`
- `_rows_to_plain_text()`
- `_save_memory_summary()`
- `_update_summary_state()`
- `_get_memory_state()`
- `_save_memory_state()`
- `_refresh_memory_state()`
- `_prune_short_memory()`
- `summarize_pending_memory()`
- `_fetch_active_summaries()`
- `cleanup_long_term_memory()`
- `_merge_old_archives_if_needed()`
- `maintain_memory_after_reply()`
- `list_memory_summaries()`
- `delete_memory_summary()`
- `get_memory_context()`

### `services\memory_view.py`
- `_text_id()`
- `_extract_message_id()`
- `_truncate()`
- `_role_label()`
- `_important_memory_url()`
- `_send_or_edit()`
- `build_memory_view_menu_markup()`
- `send_memory_view_menu()`
- `_render_short_memory()`
- `_render_summary_memory()`
- `handle_memory_view_callback()`

### `services\privacy_access.py`
- `_text_id()`
- `_is_group_chat()`
- `_cache_key()`
- `_is_pending_private_notice_cached()`
- `_mark_pending_private_notice()`
- `_mark_issued_cache()`
- `_is_issued_cached()`
- `build_privacy_password_message()`
- `_send_unlock_code_safely()`
- `ensure_privacy_password_issued()`
- `has_privacy_password_issued()`

### `services\privacy_migration.py`
- `_text_id()`
- `_has_text()`
- `_save_payload()`
- `migrate_plaintext_to_encrypted()`

### `services\privacy_session.py`
- `_text_id()`
- `_key()`
- `set_request_context()`
- `get_current_user_id()`
- `get_current_bot_id()`
- `get_current_chat_id()`
- `set_unlock_code()`
- `get_unlock_code()`
- `clear_unlock_code()`
- `is_unlocked()`

### `services\reply_style.py`
- `_text_id()`
- `_decrypt_style()`
- `_encrypt_style()`
- `_decrypt_legacy_style()`
- `normalize_style_type()`
- `_get_legacy_reply_style()`
- `get_reply_style_settings()`
- `update_reply_style_settings()`
- `delete_reply_style_settings()`

### `services\setting_auth.py`
- `_text_id()`
- `is_group_chat()`
- `_b64_encode()`
- `_b64_decode()`
- `_get_secret()`
- `_sign()`
- `create_setting_token()`
- `verify_setting_token()`
- `verify_setting_request()`
- `_fail()`

### `services\setting_sessions.py`
- `_text_id()`
- `save_setting_menu_session()`
- `pop_setting_menu_session()`

### `services\style.py`
- `_has_chat_persona()`
- `_build_chat_persona_text()`
- `_build_character_text()`
- `_build_reply_style_text()`
- `_build_facts_text()`
- `_build_memory_context_text()`
- `build_prompt()`

### `services\telegram_service.py`
- `_telegram_post()`
- `send_message()`
- `edit_message_text()`
- `answer_callback_query()`
- `delete_message()`

### `services\time_context.py`
- `_period_name()`
- `get_current_time_context()`
- `build_time_context_text()`

### `services\user_notice.py`
- `_text_id()`
- `send_once_user_notice()`

### `services\user_router.py`
- `_text_id()`
- `get_gemini_key()`
- `user_has_key()`

### `telemini\services\call_ai.py`
- `run_ai()`

### `telemini\services\database.py`
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

### `telemini\services\memory.py`
- `_text_id()`
- `_get_scope()`
- `_decrypt_safe()`
- `delete_current_memory()`
- `delete_character_memory()`
- `update_emotion()`
- `get_emotion()`
- `detect_emotion()`
- `is_memory_command()`
- `extract_memory_content()`
- `_normalize_fact_for_hash()`
- `_fact_hash()`
- `add_fact()`
- `add_important_fact()`
- `get_facts()`
- `_user_filter_sql()`
- `list_important_facts()`
- `update_important_fact()`
- `delete_important_fact()`
- `add_chat()`
- `get_chat()`
- `get_recent_chat()`

### `telemini\services\style.py`
- `_has_chat_persona()`
- `_build_chat_persona_text()`
- `_build_character_text()`
- `_build_reply_style_text()`
- `_build_facts_text()`
- `_build_memory_context_text()`
- `build_prompt()`

### `tools\encrypt_existing_plaintext.py`
- `_has_value()`
- `migrate_chat_memory()`
- `migrate_facts_memory()`
- `migrate_character_settings()`
- `migrate_chat_persona_settings()`
- `migrate_reply_style_settings()`
- `main()`

### `tools\project_snapshot.py`
- `should_ignore()`
- `get_project_files()`
- `generate_tree()`
- `analyze_python_file()`
- `extract_route_from_decorator()`
- `summarize_file()`
- `generate_project_map()`
- `main()`
