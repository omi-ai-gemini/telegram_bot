# Project Map

這份檔案由 `tools/project_snapshot.py` 自動產生。

用途：讓 ChatGPT 快速理解目前專案架構，不用每次上傳所有單檔。

## 專案根目錄

```text
C:\Projects\telemini
```

## 主要檔案列表

- `__init__.py`
- `AI_Horde尺寸與工作節點相容修正說明.txt`
- `AI_Horde生圖外帶說明.txt`
- `Bearer驗證修正說明.txt`
- `config.py`
- `docs\#U526f#U6a21#U578b#U7af6#U901f#U8207#U5716#U7247Prompt#U6574#U7406#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U56fa#U5b9a#U8eab#U4efd#U63d0#U793a#U8a5e#U751f#U5716#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U5716#U7247#U7b49#U5f85#U51fd#U5f0f#U532f#U5165#U932f#U8aa4#U4fee#U6b63#U8aaa#U660e.md`
- `docs\#U5716#U7247#U7b49#U5f85#U8207#U6a21#U578b#U5207#U63db#U4fee#U6b63#U8aaa#U660e.md`
- `docs\#U5716#U7247#U89e3#U6790#U4e0a#U9650#U8207#U7121#U56de#U61c9#U63d0#U793a#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U5716#U7247#U89e3#U6790#U6a21#U578bfallback#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U5a92#U9ad4#U8f38#U5165#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U6587#U751f#U5716#U69cb#U5716#U8207#U5716#U751f#U5716#U4fee#U6539#U529b#U5ea6#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U6587#U751f#U5716#U8207#U5716#U751f#U5716#U96d9#U6a21#U5f0f#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U670d#U52d9#U4e2d#U5fc3#U516c#U544a#U63a8#U64ad#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U670d#U52d9#U4e2d#U5fc3#U66f4#U65b0#U8aaa#U660e.md`
- `docs\#U76ee#U524d#U5c08#U6848#U6574#U5408#U72c0#U614b.md`
- `docs\AI_HORDE#U751f#U5716#U529f#U80fd#U66f4#U65b0#U8aaa#U660e.md`
- `docs\AI_HORDE生圖功能更新說明.md`
- `docs\AI_MESSAGE_ACTIONS_README.md`
- `docs\BLOCKED_RETRY_BUTTON_README.md`
- `docs\CUSTOM_STYLE_PREFIX_README.md`
- `docs\ENV_ENCRYPTION_README.md`
- `docs\HIDDEN_PASSIVE_SUMMARY_README.md`
- `docs\NORMAL_REPLY_UNIFIED_GENERATION_README.md`
- `docs\Pillow#U4f9d#U8cf4#U4fee#U5fa9#U8aaa#U660e.md`
- `docs\Pillow依賴修復說明.md`
- `docs\PRIVACY_ACCESS_README.md`
- `docs\PRIVACY_SYNC_README.md`
- `docs\PROMPT_DEBUG_DB_HOTFIX_README.md`
- `docs\PROMPT_DEBUG_README.md`
- `docs\PROMPT_DEBUG_WEB_README.md`
- `docs\REPLY_NONBLOCKING_BUTTONS_README.md`
- `docs\REPLY_RECOVERY_README.md`
- `docs\REPLY_RECOVERY_SECRET_FIX_README.md`
- `docs\SERVICE_CENTER_AUTOWEBHOOK_HOTFIX_README.md`
- `docs\SERVICE_CENTER_BUTTONS_README.md`
- `docs\SERVICE_CENTER_ENV_STAGE1_README.md`
- `docs\SETTING_LINK_AUTH_README.md`
- `docs\SMALL_UPDATE_MEMORY_VIEW_README.md`
- `docs\TEST_LAB_README.md`
- `docs\THOUGHT_WEB_VIEW_README.md`
- `docs\副模型競速與圖片Prompt整理更新說明.md`
- `docs\固定身份提示詞生圖更新說明.md`
- `docs\圖片等待函式匯入錯誤修正說明.md`
- `docs\圖片等待與模型切換修正說明.md`
- `docs\圖片解析上限與無回應提示更新說明.md`
- `docs\圖片解析模型fallback更新說明.md`
- `docs\媒體輸入更新說明.md`
- `docs\文生圖構圖與圖生圖修改力度更新說明.md`
- `docs\文生圖與圖生圖雙模式更新說明.md`
- `docs\服務中心公告推播更新說明.md`
- `docs\服務中心更新說明.md`
- `docs\目前專案整合狀態.md`
- `handlers\__init__.py`
- `handlers\call_handler.py`
- `handlers\message_handler.py`
- `main.py`
- `prompt#U5916#U5e36#U8aaa#U660e.txt`
- `prompt外帶說明.txt`
- `README_#U8986#U84cb#U8aaa#U660e.txt`
- `README_覆蓋說明.txt`
- `requirements.txt`
- `routes\admin.py`
- `routes\image_gen.py`
- `routes\local_ai_tasks.py`
- `routes\prompt_debug.py`
- `routes\setting.py`
- `routes\thought.py`
- `service_center\__init__.py`
- `service_center\db.py`
- `service_center\handler.py`
- `service_center\scheduler.py`
- `service_center\telegram.py`
- `services\__init__.py`
- `services\ai_actions.py`
- `services\aihorde_service.py`
- `services\aihorde_text_service.py`
- `services\bot_router.py`
- `services\call_ai.py`
- `services\character.py`
- `services\chat_persona.py`
- `services\comfyui_service.py`
- `services\commands.py`
- `services\crypto_box.py`
- `services\crypto_env.py`
- `services\database.py`
- `services\encrypted_store.py`
- `services\gemini_service.py`
- `services\image_actions.py`
- `services\image_auth.py`
- `services\image_jobs.py`
- `services\image_prepare.py`
- `services\image_prompt.py`
- `services\image_store.py`
- `services\local_ai_gateway_client.py`
- `services\local_ai_tasks.py`
- `services\media_ai.py`
- `services\memory.py`
- `services\memory_summary.py`
- `services\memory_view.py`
- `services\model_mode.py`
- `services\privacy_access.py`
- `services\privacy_migration.py`
- `services\privacy_session.py`
- `services\prompt_debug.py`
- `services\qwen_service.py`
- `services\reply_model_router.py`
- `services\reply_style.py`
- `services\runtime_cache.py`
- `services\setting_auth.py`
- `services\setting_sessions.py`
- `services\style.py`
- `services\telegram_service.py`
- `services\time_context.py`
- `services\user_notice.py`
- `services\user_router.py`
- `static\image_reference\#U57fa#U6e96#U5716#U653e#U7f6e#U8aaa#U660e.txt`
- `static\image_reference\seed.txt`
- `static\image_reference\基準圖放置說明.txt`
- `templates\character_form.html`
- `templates\chat_persona_form.html`
- `templates\developer.html`
- `templates\image_gen_form.html`
- `templates\image_library.html`
- `templates\image_prompt_debug.html`
- `templates\important_memory_form.html`
- `templates\index.html`
- `templates\login.html`
- `templates\manual.html`
- `templates\prompt_debug_compare.html`
- `templates\prompt_debug_detail.html`
- `templates\prompt_debug_list.html`
- `templates\reply_style_form.html`
- `templates\thought_view.html`
- `test_comfy_api.py`
- `test_lab\__init__.py`
- `test_lab\db.py`
- `test_lab\gemini.py`
- `test_lab\README.md`
- `test_lab\routes.py`
- `test_lab\service.py`
- `test_lab\telegram.py`
- `test_lab\templates\test_lab_form.html`
- `tools\apply_blocked_retry_patch.py`
- `tools\encrypt_existing_plaintext.py`
- `tools\project_snapshot.py`
- `workflows\img&txt2img_basic_api.json`
- `workflows\txt2img_basic_api.json`
- `使用說明.txt`
- `修改檔案清單.txt`
- `全寫真防肖像改版說明.txt`
- `副模型真實對話角色修正說明.txt`
- `副模型競速與圖片Prompt覆蓋說明.txt`
- `副模型競速與生圖流程檢查結果.txt`
- `副模型降版說明.txt`
- `匝道重連任務回收修正說明.txt`
- `啟動錯誤修正說明.txt`
- `固定身份提示詞生圖_最新版相容修正版覆蓋說明.txt`
- `圖片模型fallback覆蓋說明.txt`
- `圖片等待與模型切換覆蓋說明.txt`
- `媒體輸入覆蓋說明.txt`
- `局部遮罩畫筆修復說明.txt`
- `更新說明.txt`
- `服務中心公告推播覆蓋說明.txt`
- `服務中心硬檢查覆蓋說明.txt`
- `服務中心管理員判定修復說明.txt`
- `本機AI閘道\app.py`
- `本機AI閘道\cloudflared-config範例.yml`
- `本機AI閘道\Cloudflare設定步驟.txt`
- `本機AI閘道\gateway_config.example.json`
- `本機AI閘道\gateway_config.json`
- `本機AI閘道\requirements.txt`
- `本機AI閘道\設定說明.txt`
- `本次修復說明.txt`
- `本次修改說明.txt`
- `模型切換共用路由修正說明.txt`
- `模式-使用說明.txt`
- `生圖功能檢查結果.txt`
- `生圖排隊狀態與失敗通知覆蓋說明.txt`
- `生圖改版相容性檢查結果.txt`
- `生圖雙模式改版檢查結果.txt`
- `生圖雙模式改版覆蓋說明.txt`
- `生圖雙模式本次覆蓋說明.txt`
- `補丁套用說明.txt`
- `補丁覆蓋說明.txt`
- `覆蓋方式.txt`
- `覆蓋檔案清單.txt`
- `覆蓋說明.txt`
- `遮罩局部修改外帶說明.txt`
- `遮罩生圖修正說明.txt`
- `開場-更新說明.txt`
- `隱私版檢查結果.txt`

## Python 路由總覽

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

### `routes\image_gen.py`
- `/image/generate` → `image_generate_page`
- `/image/generate` → `image_generate_submit`
- `/image/prompt_debug/<int:job_id>` → `image_prompt_debug_page`
- `/setting/images` → `image_library_page`
- `/setting/images/preview/<identifier>` → `image_library_preview`
- `/setting/images/rename` → `image_library_rename`
- `/setting/images/delete` → `image_library_delete`

### `routes\prompt_debug.py`
- `/prompt_debug` → `prompt_debug_list_page`
- `/prompt_debug/<int:log_id>` → `prompt_debug_detail_page`
- `/prompt_debug/compare` → `prompt_debug_compare_page`

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

### `test_lab\routes.py`
- `/test_lab` → `test_lab_page`
- `/test_lab/save` → `save_test_lab_page`

## Python 函式總覽

### `config.py`
- `_env_int()`

### `handlers\call_handler.py`
- `_setting_fallback_text()`
- `_send_script_opening()`
- `_cleanup_session_bound_menu()`
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

### `routes\image_gen.py`
- `_image_privacy_headers()`
- `_decode_mask_data_url()`
- `_token()`
- `_build_qwen_source_prompt()`
- `_auth()`
- `_render_generate()`
- `image_generate_page()`
- `image_generate_submit()`
- `image_prompt_debug_page()`
- `image_library_page()`
- `image_library_preview()`
- `image_library_rename()`
- `image_library_delete()`

### `routes\local_ai_tasks.py`
- `_secret()`
- `_verify_worker()`
- `_auth_guard()`
- `local_ai_next_task()`
- `local_ai_task_heartbeat()`
- `local_ai_task_result()`
- `local_ai_task_fail()`

### `routes\prompt_debug.py`
- `_auth_from_request()`
- `prompt_debug_list_page()`
- `prompt_debug_detail_page()`
- `prompt_debug_compare_page()`

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

### `service_center\db.py`
- `_text_id()`
- `init_service_center_db()`
- `upsert_service_center_subscriber()`
- `mark_service_center_subscriber_inactive()`
- `list_service_center_subscribers()`
- `list_announcements()`
- `list_pushable_announcements()`
- `get_latest_announcement()`
- `create_announcement()`
- `claim_announcement_delivery()`
- `mark_announcement_pushed()`
- `mark_announcement_delivery_result()`
- `get_scheduler_state()`
- `set_scheduler_state()`

### `service_center\handler.py`
- `_text_id()`
- `_pending_key()`
- `_set_pending()`
- `_pop_pending()`
- `_clear_pending()`
- `is_service_center_bot()`
- `_admin_ids()`
- `is_service_center_admin()`
- `_main_menu_markup()`
- `_back_menu_markup()`
- `_cancel_input_markup()`
- `_manual_markup()`
- `_home_text()`
- `_format_announcement()`
- `_notice_text()`
- `_create_bot_text()`
- `_wifi_text()`
- `_gemini_text()`
- `_manual_text()`
- `_manual_section_text()`
- `_manual_title_by_action()`
- `_status_text()`
- `_admin_text()`
- `_text_by_action()`
- `_looks_like_bot_token()`
- `_looks_like_gemini_key()`
- `_mask_secret()`
- `_delete_sensitive_user_message()`
- `_handle_bot_token_input()`
- `_handle_gemini_key_input()`
- `_handle_announce_command()`
- `handle_service_center_message()`
- `handle_service_center_callback()`

### `service_center\scheduler.py`
- `_text_id()`
- `_today_key()`
- `_is_push_time()`
- `_format_announcement_push()`
- `push_pending_announcements_once()`
- `_scheduler_loop()`
- `start_service_center_announcement_scheduler()`

### `service_center\telegram.py`
- `_telegram_post()`
- `send_message()`
- `edit_message_text()`
- `answer_callback_query()`
- `delete_message()`
- `get_bot_info_by_token()`
- `setup_game_bot_webhook()`
- `_service_center_token()`
- `get_service_center_webhook_url()`
- `setup_service_center_webhook()`
- `get_service_center_webhook_info()`

### `services\ai_actions.py`
- `_text_id()`
- `_is_group_chat()`
- `_should_show_ai_buttons_for_mode()`
- `_should_show_ai_buttons()`
- `_hidden_keyboard_key()`
- `_hidden_keyboard_markup()`
- `_remove_keyboard_markup()`
- `build_blocked_reply_keyboard()`
- `send_blocked_reply_message()`
- `_delete_message_later()`
- `_save_hidden_keyboard_session()`
- `_pop_hidden_keyboard_session()`
- `_close_hidden_keyboard()`
- `_purge_expired_thought_cache()`
- `_get_or_create_ai_thought_token()`
- `get_ai_thought_url()`
- `build_ai_action_keyboard()`
- `_get_latest_ai_action_id()`
- `_create_latest_hidden_action_from_memory()`
- `_extract_telegram_message_id()`
- `send_hidden_ai_action_menu()`
- `handle_hidden_keyboard_message()`
- `cache_ai_thought_summary()`
- `clear_ai_thought_summary()`
- `get_ai_thought_summary_by_token()`
- `_split_gemini_result()`
- `create_ai_message_action()`
- `update_action_telegram_message_id()`
- `get_ai_message_action()`
- `create_pending_edit()`
- `pop_active_pending_edit()`
- `start_edit_ai_message()`
- `process_pending_edit_message()`
- `_load_generation_context()`
- `_generate_reply()`
- `regenerate_ai_message()`
- `continue_ai_message()`
- `_resave_current_custom_reply_style()`
- `_run_manual_summary_after_cleanup()`
- `passive_summarize_memory()`
- `repair_blocked_summary_and_resummarize()`
- `run_passive_summarize_memory_in_thread()`
- `run_repair_blocked_summary_in_thread()`
- `reply_ai_message()`
- `run_reply_ai_message_in_thread()`
- `run_regenerate_in_thread()`
- `run_continue_in_thread()`
- `_worker()`

### `services\aihorde_service.py`
- `_bool_env()`
- `_keys()`
- `_headers()`
- `_json_or_error()`
- `_error_message()`
- `_clamp()`
- `_looks_like_color_only_edit()`
- `_pick_denoising_strength()`
- `submit_image_request()`
- `check_image_request()`
- `get_image_result()`
- `cancel_image_request()`
- `download_generated_image()`

### `services\aihorde_text_service.py`
- `_keys()`
- `_headers()`
- `_json_or_error()`
- `_error_message()`
- `get_secondary_model_label()`
- `_clean_generated_text()`
- `_llama3_prompt()`
- `_secondary_system_text()`
- `_llama3_chat_prompt()`
- `_clean_chat_reply_output()`
- `submit_text_request()`
- `get_text_status()`
- `cancel_text_request()`
- `generate_text()`
- `_save_secondary_debug()`
- `generate_chat_reply()`
- `_extract_json_payload()`
- `_ensure_string_list()`
- `_join_unique()`
- `_mode_profile()`
- `_legacy_image_prompt_organizer()`
- `_structured_image_prompt_organizer()`
- `organize_image_prompt()`

### `services\bot_router.py`
- `_decrypt_bot_token_safe()`
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
- `_finalize_generated_reply()`
- `_send_generated_reply()`
- `run_ai()`
- `run_blocked_reply_retry()`
- `run_blocked_reply_race()`
- `run_reply_recovery()`
- `worker()`

### `services\character.py`
- `_text_id()`
- `_clean_text()`
- `_cache_key()`
- `clear_character_settings_cache()`
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
- `_cache_key()`
- `clear_chat_persona_settings_cache()`
- `_decrypt_field()`
- `_encrypt_field()`
- `has_chat_persona_settings()`
- `get_chat_persona_settings()`
- `update_chat_persona_settings()`
- `delete_chat_persona_settings()`

### `services\comfyui_service.py`
- `_workflow_seed()`
- `_load_txt2img_workflow_template()`
- `build_txt2img_workflow()`
- `_post_json()`
- `queue_prompt()`
- `interrupt()`
- `_local_task_id_from_prompt()`
- `_get_history()`
- `_pick_image_meta()`
- `_safe_delete_direct_temp()`
- `_delete_direct_history()`
- `_download_view()`
- `wait_for_prompt_image()`

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
- `_encrypt_db_secret_safe()`
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
- `_image_parse_result()`
- `_image_model_key()`
- `_now_ts()`
- `_seconds_until_next_pacific_midnight()`
- `_is_image_model_temporarily_disabled()`
- `_disable_image_model_until_reset()`
- `_classify_image_error()`
- `_image_models_to_try()`
- `ask_gemini_image_to_text()`
- `ask_gemini_prompt()`
- `ask_gemini()`
- `summarize_memory()`

### `services\image_actions.py`
- `_text()`
- `_base_url()`
- `get_action_identity()`
- `get_image_generation_url()`
- `get_image_library_url()`
- `load_action_context()`
- `send_hidden_image_link()`
- `send_image_command_link()`

### `services\image_auth.py`
- `_text()`
- `_secret()`
- `_b64e()`
- `_b64d()`
- `create_image_token()`
- `verify_image_token()`

### `services\image_jobs.py`
- `_text()`
- `_extract_message_id()`
- `_cancel_markup()`
- `_prompt_debug_url()`
- `_job_status_markup()`
- `_delete_notice_markup()`
- `_encrypt_prompt()`
- `_decrypt_prompt()`
- `_count_active()`
- `create_image_job()`
- `_get_job()`
- `_split_prompt_preview()`
- `get_image_job_prompt_debug()`
- `_claim_job()`
- `_update_job()`
- `_elapsed_seconds()`
- `_format_duration()`
- `_queue_text()`
- `_edit_status_message()`
- `_delete_status_message()`
- `_send_result_notice()`
- `_fail()`
- `_cancel()`
- `_processing_text()`
- `_load_system_reference()`
- `_resolve_reference()`
- `_save_generated_telegram_photo()`
- `_job_cancel_requested()`
- `_is_local_task_prompt()`
- `_local_task_id_from_prompt()`
- `_qwen_retryable_error()`
- `_wait_for_qwen_retake()`
- `_finish_omi_txt2img_result()`
- `_process_comfy_txt2img()`
- `process_image_job()`
- `run_image_job_in_thread()`
- `cancel_job_for_user()`
- `recover_active_image_jobs()`

### `services\image_prepare.py`
- `_round_to_step()`
- `_choose_dynamic_output_size()`
- `_prepare_mask_canvas()`
- `prepare_img2img_source()`

### `services\image_prompt.py`
- `_clean()`
- `_matches_any()`
- `_portrait_requested()`
- `_fixed_tag_prompt()`
- `_request_sections()`
- `build_image_prompt()`

### `services\image_store.py`
- `_text()`
- `init_image_tables()`
- `_new_code()`
- `save_image_asset()`
- `save_incoming_photo_message()`
- `list_image_assets()`
- `get_image_asset()`
- `download_image_asset()`
- `rename_image_asset()`
- `delete_image_asset()`

### `services\local_ai_gateway_client.py`
- `gateway_requested()`
- `gateway_enabled()`
- `gateway_reverse_enabled()`
- `gateway_config_error()`
- `_body_bytes()`
- `_auth_headers()`
- `_request()`
- `gateway_post_json()`
- `gateway_get_json()`
- `gateway_get_bytes()`

### `services\local_ai_tasks.py`
- `init_local_ai_task_tables()`
- `create_local_ai_task()`
- `cancel_local_ai_task()`
- `claim_next_local_ai_task()`
- `heartbeat_local_ai_task()`
- `complete_local_ai_task()`
- `fail_local_ai_task()`
- `fetch_local_ai_task_result()`
- `wait_for_local_ai_task_result()`
- `cleanup_old_local_ai_tasks()`
- `encode_result_bytes()`
- `decode_result_bytes()`

### `services\media_ai.py`
- `_text()`
- `_pending_photo_key()`
- `_cancel_pending_timer()`
- `_missing_config()`
- `send_unsupported_media_message()`
- `_download_image()`
- `_register_pending_photo()`
- `_build_photo_user_text()`
- `_dispatch_photo_item()`
- `_recover_buffered_text_after_photo_failure()`
- `_remove_pending_photo()`
- `_fail_pending_photo()`
- `_photo_wait_timeout()`
- `_complete_pending_photo()`
- `queue_text_for_pending_photo()`
- `handle_photo_message()`
- `handle_sticker_message()`
- `run_photo_message_in_thread()`
- `run_sticker_message_in_thread()`
- `run_unsupported_media_in_thread()`

### `services\memory.py`
- `_text_id()`
- `_get_scope()`
- `_to_taipei_datetime()`
- `_format_chat_time_label()`
- `_history_item()`
- `_facts_cache_prefix()`
- `clear_facts_cache()`
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
- `get_chat_for_prompt()`
- `list_recent_chat_memory()`
- `delete_chat_memory_item()`
- `get_recent_chat()`

### `services\memory_summary.py`
- `_notify_summary_blocked()`
- `_is_summary_blocked()`
- `_text_id()`
- `_get_scope()`
- `_memory_context_cache_prefix()`
- `clear_memory_context_cache()`
- `_decrypt_safe()`
- `_fetch_unsummarized_rows()`
- `_rows_to_plain_text()`
- `_save_memory_summary()`
- `_update_summary_state()`
- `_get_memory_state()`
- `_save_memory_state()`
- `_refresh_memory_state()`
- `_prune_short_memory()`
- `count_pending_summary_messages()`
- `summarize_pending_memory()`
- `_fetch_active_summaries()`
- `cleanup_long_term_memory()`
- `_merge_old_archives_if_needed()`
- `repair_blocked_summary_attempt()`
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

### `services\model_mode.py`
- `_text()`
- `get_api_model_mode()`
- `set_api_model_mode()`
- `toggle_api_model_mode()`
- `_mode_text()`
- `handle_models_deputy_command()`

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

### `services\prompt_debug.py`
- `_text_id()`
- `_token_secret()`
- `_sign()`
- `create_prompt_debug_token()`
- `verify_prompt_debug_token()`
- `_base_url()`
- `build_prompt_debug_url()`
- `build_prompt_debug_compare_url()`
- `save_prompt_debug_log()`
- `update_prompt_debug_log()`
- `list_prompt_debug_logs()`
- `get_prompt_debug_log()`
- `_format_dt()`
- `_row_to_summary()`
- `_row_to_detail()`
- `send_prompt_debug_link()`

### `services\qwen_service.py`
- `_clean_text()`
- `_normalize_visual_terms()`
- `_add_terms()`
- `_remove_terms()`
- `_has_claw_clip_updo_request()`
- `_apply_visual_translation_locks()`
- `_portrait_requested()`
- `_apply_identity_and_composition_locks()`
- `_post_generate()`
- `_post_chat()`
- `get_secondary_model_label()`
- `generate_chat_reply()`
- `_strip_code_fence()`
- `_extract_json()`
- `_infer_identity()`
- `_infer_gender()`
- `build_face_prompts()`
- `organize_image_prompt()`

### `services\reply_model_router.py`
- `_normalize_main()`
- `_normalize_secondary()`
- `generate_reply_by_mode()`

### `services\reply_style.py`
- `_text_id()`
- `_cache_key()`
- `clear_reply_style_settings_cache()`
- `_decrypt_style()`
- `_encrypt_style()`
- `_decrypt_legacy_style()`
- `normalize_style_type()`
- `_get_legacy_reply_style()`
- `get_reply_style_settings()`
- `update_reply_style_settings()`
- `delete_reply_style_settings()`
- `resave_existing_reply_style_settings()`

### `services\runtime_cache.py`
- `_now()`
- `get_cache()`
- `set_cache()`
- `delete_cache()`
- `clear_cache()`
- `get_cache_stats()`

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
- `save_setting_menu_session_async()`
- `save_setting_menu_session()`
- `pop_setting_menu_session()`
- `_job()`

### `services\style.py`
- `_has_chat_persona()`
- `_build_chat_persona_text()`
- `_build_character_text()`
- `_build_custom_reply_style_text()`
- `_build_reply_style_text()`
- `_build_facts_text()`
- `_build_memory_context_text()`
- `build_prompt()`

### `services\telegram_service.py`
- `_telegram_post()`
- `send_message()`
- `send_photo_bytes()`
- `edit_message_text()`
- `answer_callback_query()`
- `delete_message()`
- `get_file()`
- `_extract_file_path()`
- `download_file_bytes()`
- `guess_mime_type_from_file_path()`

### `services\time_context.py`
- `_period_name()`
- `get_current_time_context()`
- `build_time_context_text()`

### `services\user_notice.py`
- `_text_id()`
- `send_once_user_notice()`

### `services\user_router.py`
- `_text_id()`
- `_decrypt_gemini_key_safe()`
- `get_gemini_key()`
- `clear_gemini_key_cache()`
- `user_has_key()`

### `test_comfy_api.py`
- `load_workflow()`
- `fill_workflow()`
- `submit_workflow()`
- `wait_for_result()`
- `print_output_files()`
- `main()`

### `test_lab\db.py`
- `init_test_lab_db()`

### `test_lab\gemini.py`
- `_safe_response_text()`
- `ask_test_gemini()`

### `test_lab\routes.py`
- `test_lab_page()`
- `save_test_lab_page()`

### `test_lab\service.py`
- `_text_id()`
- `make_test_user_id()`
- `_plain_api_key()`
- `ensure_profile()`
- `get_profile()`
- `save_profile_settings()`
- `save_api_key()`
- `set_session()`
- `get_session()`
- `is_test_active()`
- `is_test_awaiting_api_key()`
- `is_test_awaiting_prompt_input()`
- `should_skip_main_user_config()`
- `add_memory()`
- `list_memory()`
- `list_summaries()`
- `_history_text()`
- `_summary_text()`
- `build_chat_prompt()`
- `generate_test_reply()`
- `summarize_test_memory()`
- `save_prompt_version()`
- `_prompt_saved_message()`
- `generate_prompt()`
- `_token_secret()`
- `create_page_token()`
- `verify_page_token()`
- `build_setting_url()`
- `send_long_test_message()`
- `handle_test_lab_message()`

### `test_lab\telegram.py`
- `send_test_message()`

### `tools\apply_blocked_retry_patch.py`
- `patch_call_ai()`
- `patch_call_handler()`
- `main()`

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

### `本機AI閘道\app.py`
- `_load_gateway_config()`
- `_verify_request()`
- `_auth_guard()`
- `_proxy_json()`
- `ollama_generate()`
- `ollama_chat()`
- `comfy_prompt()`
- `comfy_interrupt()`
- `comfy_history()`
- `_temp_root()`
- `_cleanup_stale_temp_files()`
- `_stale_cleanup_loop()`
- `_clear_comfy_history_on_start()`
- `_safe_temp_path()`
- `_render_headers()`
- `_render_get()`
- `_render_post()`
- `_pick_image_meta()`
- `_history_error_message()`
- `_delete_temp_and_history()`
- `_comfy_run_prompt()`
- `_ollama_generate()`
- `_ollama_chat()`
- `_task_heartbeat_loop()`
- `_process_render_task()`
- `_render_worker_loop()`
- `comfy_view()`
- `_privacy_headers()`
