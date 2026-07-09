# Service Center 五個按鈕調整

## 修改檔案

- `service_center/handler.py`

## 更新內容

服務中心主選單改成五個主要按鈕：

1. 公告事項：所有歷史公告
2. 建立Bot：我盡量簡單的告訴你怎麼創建新的機器人
3. Telemini Wifi：新的機器人連線到遊戲程式
4. Gemini API：新增或更改AI連線
5. 操作說明：遊戲內可用的操作和使用方法

## 行為

- 新增 `svc:wifi` callback。
- 新增 `_wifi_text()` 說明頁。
- 主選單移除「服務狀態」按鈕。
- `/status` 指令仍保留，可用於開發者檢查狀態。
- 不新增任何 DB table。
- 不影響主遊戲流程。

## 測試

```bash
python -m py_compile service_center/handler.py
```
