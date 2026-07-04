# Telemini AI 回覆操作按鈕

## 功能

私聊中每次 AI 回覆下方會附上小按鈕：

```text
[✏️改] [🔁重跑] [▶️接續]
```

群組先保留延伸，不顯示這三個按鈕。

## 行為

### ✏️改

1. 使用者按下「✏️改」。
2. bot 發一則臨時提示，請使用者輸入替換文字。
3. 使用者下一則文字會被視為修改稿。
4. 修改稿不送 Gemini、不寫入短期記憶。
5. 系統用 `editMessageText` 修改原本那則 AI 訊息。
6. 同步更新原本那筆 `chat_memory` 的 assistant 內容。
7. 自動刪除 bot 臨時提示與使用者修改稿。

### 🔁重跑

1. 使用同一則原始 user 訊息重新呼叫 Gemini。
2. 用新回覆覆蓋原本那則 AI 訊息。
3. 同步更新原本那筆 assistant `chat_memory`。
4. 不新增 user 記憶、不新增 assistant 記憶。

### ▶️接續

1. 不需要使用者再輸入。
2. Gemini 根據目前對話、場景、角色、記憶與現實時間自然接續下一句。
3. 發送新的 AI 訊息。
4. 新增一筆 assistant `chat_memory`。
5. 新訊息下方同樣會附上三個操作按鈕。

## 新增資料表

```text
ai_message_actions
pending_ai_actions
```

`ai_message_actions` 用於對應 Telegram 訊息與 `chat_memory`。

`pending_ai_actions` 用於保存「按下 ✏️改 後等待下一句文字」的暫存狀態，預設 5 分鐘失效。

## 時間上下文

每次 Gemini 回覆前會即時計算台灣時間，不寫入 DB。

提供給 prompt 的內容包含：

```text
時區：Asia/Taipei（台灣時間）
日期
星期
時間
時段
```

聊天模式可以自然使用現實時間；劇場模式除非使用者明確提到，否則不主動用現實時間干擾劇情時間。
