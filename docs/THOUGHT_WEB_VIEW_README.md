# Telemini Gemini 推理摘要網頁查看包

## 更新內容

AI 回覆下方按鈕改為：

```text
[✏️][🔁][🧠][▶️]
```

其中 `🧠` 改成網址按鈕，點擊後開啟單筆推理摘要網頁。

## 行為

- 推理摘要只放在 Render 記憶體快取。
- 不寫入 `chat_memory`。
- 不寫入長期記憶。
- 不寫入資料庫。
- 不寫入檔案。
- Render 重啟或快取過期後，網頁會顯示「推理摘要已過期」。
- 網頁只顯示該筆回覆對應的推理摘要，不做列表頁。

## 新增檔案

- `routes/thought.py`
- `templates/thought_view.html`
- `docs/THOUGHT_WEB_VIEW_README.md`

## 覆蓋檔案

- `main.py`
- `handlers/call_handler.py`
- `services/ai_actions.py`
- `services/call_ai.py`
- `services/gemini_service.py`

## 必要環境變數

需要有：

```text
BASE_URL=https://你的-render網址
```

`🧠` 按鈕會用 `BASE_URL` 產生：

```text
/thought/<隨機token>
```

如果沒有設定 `BASE_URL`，按鈕會退回 callback 提示，不會打開網頁。

## 注意

Gemini API 回傳的是 thought summary，不是完整逐字內部推理。


## 立即顯示過期的排查

如果剛產生的最新回覆，點 `🧠` 就立刻顯示「推理摘要已過期」，通常有兩種原因：

1. Render / Gunicorn 使用多個 worker。
   - webhook 產生推理摘要時在 A process。
   - 使用者打開 `/thought/<token>` 時被分到 B process。
   - 因為快取只在記憶體，不寫 DB，所以 B process 找不到 token。
   - 解法：Render Start Command 建議使用單 worker，例如：

```bash
gunicorn main:app --workers 1 --threads 8 --timeout 120
```

2. Gemini 這次沒有回傳 thought summary。
   - 這版會顯示「這筆沒有推理摘要」，不再誤顯示成過期。
   - Render log 會印出 `GEMINI extracted lengths` 與 `THOUGHT cache saved`，可用來確認。
