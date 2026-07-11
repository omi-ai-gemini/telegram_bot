# Pillow 依賴說明

目前 Pillow 不再用於系統基準圖遮罩。

它只用於玩家上傳圖片或聊天室參考圖片：

- 讀取 JPG／PNG／WEBP
- 修正 EXIF 方向
- 等比例縮放並裁切為 896×1152
- 禁止直接拉伸人物比例

`requirements.txt` 保留：

```text
Pillow==12.3.0
```

Pillow 採延遲安全匯入，安裝異常時不會讓 Gunicorn 在匯入階段直接崩潰；只會讓該次自訂圖片任務回報依賴缺失。
