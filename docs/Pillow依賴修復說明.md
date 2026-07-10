# Pillow 依賴修復

遮罩生圖會使用 Pillow 處理基準圖、最終畫布與 inpainting 遮罩。

已修正：

- `requirements.txt` 新增 `Pillow==12.3.0`
- Pillow 12 支援 Python 3.14
- 若部署環境未成功安裝 Pillow，不再讓整個 Bot 在 Gunicorn 匯入階段崩潰
- 缺少依賴時只會讓該次生圖任務失敗，Render log 會顯示明確原因

部署後 Render 會在 Build 階段自動安裝 Pillow，不需要新增環境變數。
