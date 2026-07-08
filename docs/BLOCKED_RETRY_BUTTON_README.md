# 內容被安全阻擋按鈕流程修正

## 目的

把「內容被安全阻擋」訊息下方的 🗣️ 按鈕改成專用重跑流程。

## 新行為

按下阻擋訊息下面的 🗣️：

1. 先刪除阻擋提示訊息。
2. 不走一般 🔁 重跑，所以不刪除任何 AI 正文訊息。
3. 讀取短期記憶最後一筆。
4. 最後一筆必須是 `user`。
5. 不重複新增 user 記憶。
6. 直接用最後一筆 user 記憶重新呼叫 Gemini，補送一則新的 assistant 回覆。

## 修改檔案

- `services/call_ai.py`
  - 新增 `run_blocked_reply_retry()`。
- `handlers/call_handler.py`
  - `blocked_reply_debug` 先刪除阻擋提示訊息。
  - 再呼叫 `run_blocked_reply_retry()` 補送新的 assistant 回覆。

## 套用

```powershell
python tools\apply_blocked_retry_patch.py
python -m py_compile services\call_ai.py handlers\call_handler.py
git add services/call_ai.py handlers/call_handler.py docs/BLOCKED_RETRY_BUTTON_README.md tools/apply_blocked_retry_patch.py
git commit -m "fix blocked reply retry button"
git push
```
