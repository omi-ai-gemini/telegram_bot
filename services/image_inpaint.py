"""舊遮罩生圖相容占位檔。

目前生圖流程已改為：
- 文生圖：txt2img
- 圖生圖：img2img

本模組不再被任何執行路徑匯入，保留檔名只避免舊部署差異造成混淆。
"""

INPAINTING_DISABLED = True
