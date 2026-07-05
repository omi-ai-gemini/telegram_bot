# Telemini 自訂風格全局前綴更新包

## 覆蓋檔案

- `services/style.py`

## 更新內容

新增程式碼固定前綴：

```python
CUSTOM_REPLY_STYLE_PREFIX
```

用途：

1. 這段固定寫在程式碼，不進資料庫。
2. 不開放網頁修改。
3. 聊天模式自訂風格與劇場模式自訂風格送進 Gemini 前，會先接上這段前綴。
4. 使用者已經儲存在 DB 的自訂風格不會被改動。
5. 沒有自訂風格時仍維持原本預設風格流程。

## Prompt 結構

```text
BASE_STYLE
RESPONSE_RULES
...
本次回覆樣式：
  目前使用：聊天/劇場模式自訂回覆樣式
  自訂風格全局前綴
  使用者自訂聊天/劇場回覆樣式
```

## 測試

已執行：

```bash
python -m py_compile services/style.py
```
