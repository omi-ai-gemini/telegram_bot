# Telemini 副模型競速與圖片 Prompt 整理更新

## 1. AI Horde 副文字模型

新增：

- `services/aihorde_text_service.py`
- `services/model_mode.py`

預設副模型：

```text
koboldcpp/L3-8B-Stheno-v3.2
koboldcpp/mini-magnum-12b-v1.1
```

兩個名稱會一起送進 AI Horde，由當下可用工作節點先接單。可在 Render 改成：

```text
AI_HORDE_TEXT_MODELS=模型一,模型二
```

沿用原本：

```text
AI_HORDE_API_KEY_1
AI_HORDE_API_KEY_2
```

不需要新增第三把 Key。

## 2. 安全阻擋按鈕

一般回覆出現「內容被安全阻擋」時，按鈕改為：

```text
⚡ 副模型競速
```

按下後：

1. 目前聊天室後續回覆模式切成副模型。
2. Gemini 與 AI Horde 同時生成。
3. 第一個有效回覆勝出。
4. Gemini 安全阻擋或空回覆不算有效結果。
5. Gemini 先完成時，程式會通知 AI Horde 取消仍在等待的文字任務。
6. 競速狀態訊息完成後會自動刪除。

重要 Log：

```text
MODEL RACE START
MODEL RACE BRANCH RESULT
MODEL RACE WINNER
MODEL RACE ERROR
```

## 3. 主副模型切換指令

```text
/modes_api
```

不帶參數時，主模型與副模型互相切換。

```text
/modes_api main
/modes_api secondary
/modes_api status
```

- `main`：後續一般回覆走 Gemini。
- `secondary`：後續一般回覆直接走 AI Horde。
- `status`：只查看目前模式。

切換與查詢會寫入 `MODEL MODE COMMAND` / `MODEL MODE SET` Log。

狀態保存在：

```text
api_model_modes
```

範圍為 `user_id + bot_id + chat_id`，不同聊天室互不影響。

## 4. 圖片 Prompt 整理流程

舊流程：

```text
網頁提示詞 → 圖片模型
```

新流程：

```text
網頁提示詞／預設提示詞
→ Telegram 顯示「prompt生成中」
→ AI Horde 副文字模型整理成英文畫面 Prompt
→ 圖片 API 接受任務
→ 原訊息改成「生圖任務已送出，正在加入排隊」
→ 原本排隊、生成、取消與完成流程照舊
```

副模型會：

- 把中文敘事改成具體英文畫面資訊。
- 保留人物、服裝、姿勢、動作、物品、鏡頭、場景與光線要求。
- 圖生圖時明確說明應修改內容與人物身份保留要求。
- 不改動原本負面提示詞。

若副模型失敗或超時：

```text
prompt生成失敗，已改用原始提示詞送出，正在加入排隊
```

圖片任務不會因此整筆失敗。任務失敗、取消或完成時，也會直接更新同一則狀態訊息並移除取消按鈕。

重要 Log：

```text
IMAGE PROMPT START
IMAGE PROMPT DONE
IMAGE PROMPT FALLBACK
SECONDARY TEXT SUBMIT PREPARED
SECONDARY TEXT SUBMIT OK
SECONDARY TEXT STATUS
SECONDARY TEXT DONE
```

Render Log 不會印出使用者 Prompt 明文，只印字數、模型、工作節點、排隊資料與錯誤摘要。

## 5. 圖片任務新增欄位

`image_generation_jobs` 會自動補上：

```text
source_prompt
prompt_generation_status
prompt_model
prompt_error
prompt_chars_before
prompt_chars_after
status_message_id
```

Prompt 內容仍使用既有 `APP_ENCRYPTION_SECRET` 加密後寫入 DB。

## 6. 可選環境變數

```text
AI_HORDE_TEXT_MODELS=koboldcpp/L3-8B-Stheno-v3.2,koboldcpp/mini-magnum-12b-v1.1
AI_HORDE_TEXT_TIMEOUT_SECONDS=150
AI_HORDE_TEXT_POLL_SECONDS=2
AI_HORDE_TEXT_MAX_CONTEXT=16384
AI_HORDE_CHAT_MAX_LENGTH=320
AI_HORDE_IMAGE_PROMPT_MAX_LENGTH=360
AI_HORDE_IMAGE_PROMPT_TIMEOUT_SECONDS=120
```

## 7. 隱私提醒

AI Horde 是社群工作節點。副模型模式與圖片 Prompt 整理會把對應文字送到外部工作節點；程式不會把 API Key、資料庫密鑰或 Telegram Bot Token放進 Prompt。


## 副模型完整 Prompt 修正

- 聊天／劇場副模型不再依字元數截斷 Prompt。
- 原本 `28000` 字元的靜默裁切已移除。
- 副模型預設上下文改為 `16384`。
- 程式會把 `build_prompt()` 產生的完整內容送出；若當下沒有足夠上下文能力的 AI Horde worker，任務會明確失敗，不會偷偷刪除中間內容後繼續生成。
- Render log 會顯示 `prompt_chars`、`max_context`、模型、worker、排隊與耗時，但不印 Prompt 明文。
