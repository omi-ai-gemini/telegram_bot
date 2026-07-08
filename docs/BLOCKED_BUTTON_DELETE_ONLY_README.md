# 嘗試重跑回覆按鈕：只刪除按鈕訊息

這包只修改：

- `handlers/call_handler.py`

行為：

1. 使用者按下「🗣️ 嘗試重跑回覆」。
2. 立刻刪除這則「內容被安全阻擋」提示訊息。
3. 保留原本 `run_blocked_reply_retry()` 流程，不改重跑邏輯。
4. 不刪 AI 正文訊息。
5. 不新增 table。
6. 不動服務中心。

測試：

```bash
python -m py_compile handlers/call_handler.py
```
