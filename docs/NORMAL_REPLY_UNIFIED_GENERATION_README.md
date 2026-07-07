# Telemini 一般回覆與按鈕回覆 prompt 統一熱修

## 修改目標

把一般使用者輸入改成和按鈕重跑 / 接續更接近的生成方式：

1. 一般輸入仍然先寫進 `chat_memory`。
2. Gemini prompt 只從 `===近期對話紀錄===` 看到最新 user 訊息。
3. 不再於 prompt 底部重複顯示：

```text
使用者：
最新輸入
```

4. `get_chat_for_prompt()` 不再用 60 分鐘 / 180 分鐘時間窗，改成固定最近 100 則短期記憶。
5. `get_chat_until()` 不再無限往前抓，改成指定 id 以前最近 100 則。
6. 接續函式本體不動；只讓底層記憶快照規則變成固定 100 則。

## 修改檔案

- `services/memory.py`
- `services/style.py`
- `services/call_ai.py`
- `services/ai_actions.py`

## 重點行為

### 一般回覆

```text
user message
→ add_chat(user)
→ get_chat_for_prompt() 取最近 100 則，其中最後一則就是最新 user
→ build_prompt() 不再額外顯示 user_text
→ Gemini 回覆
→ add_chat(assistant)
```

### 重跑

```text
找到原本 source_user_chat_id
→ get_chat_until(source_user_chat_id) 取該 id 前最近 100 則，其中最後一則就是原本 user
→ build_prompt() 不再額外顯示 user_text
→ Gemini 回覆
→ 覆蓋原 assistant 記憶
```

### 接續

接續功能仍使用原本 `CONTINUE_USER_TEXT`，沒有改 `continue_ai_message()` 函式本體。

## 測試

已執行：

```bash
python -m py_compile services/memory.py services/style.py services/call_ai.py services/ai_actions.py
```
