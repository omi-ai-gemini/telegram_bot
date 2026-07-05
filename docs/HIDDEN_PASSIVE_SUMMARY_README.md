# Telemini /hidden 被動摘要與阻擋提示修正包

覆蓋檔案：
- services/ai_actions.py
- services/call_ai.py
- services/memory_summary.py
- services/gemini_service.py
- services/reply_style.py

更新內容：

1. /hidden 第二排新增 💾
- 按下後會手動觸發被動摘要。
- 尚未滿 100 筆未摘要短期記憶時，不呼叫 Gemini，只提示目前筆數。
- 滿 100 筆時，呼叫 summarize_pending_memory(max_chunks=5)。
- 成功後會順便跑 cleanup_long_term_memory()。

2. 🗣️ 除錯回覆前新增「重新儲存既有自訂風格」
- 只重新儲存 reply_style_settings 裡已經存在的自訂風格。
- 不建立新風格。
- 不回到預設風格。
- 依目前模式重存 chat 或 theater 對應風格。

3. 安全阻擋提示補字
- 一般回覆被擋：
  內容被安全阻擋
  使用🗣️嘗試重跑回覆
- 摘要流程被擋：
  各階段阻擋訊息後面會補：
  使用🗣️嘗試重跑回覆

4. 保留上一包摘要修正
- Gemini 摘要安全阻擋會先判斷 block，再決定是否取文字。
- 刪除單筆摘要記憶時，會同步清 memory_state。
- memory_summary_state 會回退到目前仍存在摘要的最大 end_chat_id。
- 如果已無摘要，會刪除 memory_summary_state，讓後續從可用短期記憶重新計算。

部署後測試：

```bash
python -m py_compile services/ai_actions.py services/call_ai.py services/memory_summary.py services/gemini_service.py services/reply_style.py
```

Telegram 測試：
1. 私聊輸入 /hidden。
2. 確認第二排出現 💾。
3. 按 💾：
   - 未滿 100 筆時會提示未摘要筆數。
   - 滿 100 筆時會整理摘要。
4. 觸發安全阻擋時，確認訊息後面有「使用🗣️嘗試重跑回覆」。
5. 按 🗣️ 時，Render log 應出現：
   DEBUG hidden reply resave custom style
```
