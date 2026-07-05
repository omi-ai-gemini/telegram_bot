# Telemini 回覆不被推理摘要 / 按鈕阻塞修正

## 修正目標

主回覆必須優先送到 Telegram。

以下附加流程全部改成背景補掛：

```text
AI action 建立
🧠 thought summary 快取
🧠 thought URL token
[✏️][🔁][🧠][▶️] Inline Keyboard
```

## 新流程

```text
Gemini 回覆成功
→ 寫入 assistant 短期記憶
→ 立刻 sendMessage 純文字給使用者
→ 背景建立 action / thought cache / buttons
→ 用 editMessageText 把同一則訊息補上按鈕
```

## 效果

就算背景流程發生錯誤，例如：

```text
secrets 未匯入
token 建立失敗
BASE_URL 錯誤
Inline Keyboard 被 Telegram 拒收
thought summary 為空
```

使用者仍然會先收到 AI 文字回覆。

## Log

主回覆：

```text
AI SEND START len=... has_buttons=False
AI SEND RESULT ok=True telegram_message_id=...
```

背景補掛：

```text
AI ACTION CREATED action_id=...
THOUGHT cache saved ...
AI BUTTON ATTACH START ...
AI BUTTON ATTACH RESULT ok=True/False
```

如果背景補掛失敗：

```text
AI BUTTON BACKGROUND ERROR action_id=...: ...
```

這種錯誤不會再卡住主回覆。
