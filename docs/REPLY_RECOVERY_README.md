# Telemini /reply 救援指令

## 功能

新增指令：

```text
/reply
/回覆
```

用途：當 Gemini 已產生內容但 Telegram 沒送出，或上一輪真的沒有 AI 回覆時，手動補救。

## 判斷邏輯

讀取目前聊天室的短期記憶最後一筆：

```text
最後一筆是 assistant
→ 直接把最後一筆 AI 短期記憶重送到聊天室
→ 不新增 chat_memory，避免記憶變大

最後一筆是 user
→ 不重複寫 user 記憶
→ 直接用最後一筆 user 內容再打一輪 Gemini
→ 成功後寫入一筆 assistant chat_memory
```

## 按鈕

私聊中救援送出的 AI 訊息仍會附上：

```text
[✏️][🔁][🧠][▶️]
```

如果 Telegram 因為按鈕或 URL 拒收，系統會自動改成純文字重送一次，避免整則訊息消失。

## Log

新增關鍵 log：

```text
AI ACTION CREATED ...
AI SEND START ...
AI SEND RESULT ...
AI SEND RETRY ...
REPLY RECOVERY START ...
REPLY RESEND ...
REPLY GENERATE ...
```

這些 log 用來判斷是 Gemini 沒回、Telegram 沒送出、按鈕出錯，還是救援指令有成功補送。

## 回覆不被推理摘要阻塞

`/reply` 救援重送時，也改成先送純文字，再背景補掛操作按鈕與 🧠 推理摘要網址。

所以就算 thought cache / token / Inline Keyboard 發生錯誤，救援回覆仍會先送進聊天室。
