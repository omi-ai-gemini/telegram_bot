# Telemini AI Horde 生圖功能

## 完成內容

- 劇場模式 AI 訊息操作列新增 `📸`。
- `/hidden` 新增 `📸`；群組目前只顯示生圖與關閉鍵盤，方便之後測試。
- 新增 20 分鐘有效的生圖網頁。
- 新增 `/設定 → 圖片管理`。
- 使用者傳入聊天室的圖片與 AI 生成圖片會自動保存 Telegram `file_id / file_unique_id`。
- 每張圖片另外建立 8 位數圖片代號，可重新命名、查詢、刪除圖片庫紀錄。
- 網頁臨時上傳圖只存在目前 Render process 記憶體，不寫 DB、不加入圖片庫。
- 預設生圖依性別套用固定人物身份提示詞，不再把系統基準圖傳給 AI Horde。
- 聊天室圖片代號或本次上傳圖會改用 img2img，且先等比例裁切成 896×1152，禁止直接拉伸。
- 固定身份只鎖臉型、五官與基本身形；髮型、髮色、服裝、表情、姿勢、動作與場景可被本輪需求覆蓋。
- 性別必填：男／女；使用玩家參考圖時不再強塞系統固定臉型。
- 固定標籤單選，先放：浴衣、睡衣、禮服；保留補充提示詞。
- 保留完全自訂提示詞模式。
- 不呼叫 Gemini 整理生圖 prompt；直接在送往 AI Horde 的 prompt 下方加入專用「先整理訊息內容」指令。
- 每位使用者最多同時 3 張處於排隊／生成狀態。
- 兩把 AI Horde Key 依 job id 輪替使用；選中 Key 遇到驗證、額度或服務錯誤時會嘗試另一把。
- 排隊與生成合計 20 分鐘超時。
- Telegram 狀態訊息不刪除：送出、排隊預估、開始生成、失敗、取消、實際耗時。
- 狀態訊息附 `取消生圖`。
- 生圖完成只傳圖片，不附 caption；下一則訊息回報實際耗時。

## Render 必填環境變數

```text
AI_HORDE_API_KEY_1=第一個 AI Horde API Key
AI_HORDE_API_KEY_2=第二個 AI Horde API Key
BASE_URL=https://你的-render網址
SETTING_LINK_SECRET=原本設定頁使用的簽章密鑰
APP_ENCRYPTION_SECRET=原本資料加密密鑰
```

## 可選環境變數

```text
AI_HORDE_MODEL=Flux.1-Schnell fp8 (Compact)
AI_HORDE_ALLOW_NSFW=false
AI_HORDE_IMAGE_STEPS=4
AI_HORDE_CLIENT_AGENT=TeleminiAI:1.0:telegram-image-generation
```

## 系統人物身份

預設生圖不再讀取或上傳 `static/image_reference` 內的系統基準圖。

男女身份描述固定寫在：

```text
services/image_prompt.py
```

聊天室圖片代號或本次臨時上傳圖仍可作為玩家自己的參考圖片。

## 新增資料表

```text
chat_image_assets
image_generation_jobs
```

部署後第一次 request 由 `init_image_tables()` 自動建立，不用手動 SQL。

## 圖片保存規則

DB 不保存圖片 bytes，只保存：

```text
Telegram file_id
Telegram file_unique_id
8 位數圖片代號
自訂名稱
bot_id / chat_id / owner_user_id
來源、尺寸、Telegram message_id、時間
```

圖片管理的刪除只把 `is_deleted` 設為 true，不會刪除 Telegram 原始訊息。

## AI Horde 流程

```text
POST   /api/v2/generate/async
GET    /api/v2/generate/check/{id}
GET    /api/v2/generate/status/{id}
DELETE /api/v2/generate/status/{id}
```

模型預設參數：

```text
model: Flux.1-Schnell fp8 (Compact)
sampler: k_euler
steps: 4
cfg_scale: 1
source_processing: inpainting
source_mask: 動態產生的人物／場景重繪遮罩
output: 896×1152
n: 1
```

## 測試

```powershell
python -m compileall -q .
```

Telegram：

1. 確認男女基準圖存在；程式會自動等比例置中並建立遮罩。
2. Render 加入兩把 AI Horde Key 並重新部署。
3. 切到劇場模式，讓 AI 回覆一則訊息。
4. 點回覆下方 `📸`。
5. 選性別、AI／使用者訊息、標籤後送出。
6. 確認聊天室依序收到排隊訊息、預估時間、生成訊息、圖片與實際耗時。
7. 連續送出 3 張；第 4 張應被阻擋。
8. 點 `取消生圖`，確認聊天室收到取消結果。
9. 傳一張圖片進聊天室，再從 `/設定 → 圖片管理` 查看代號、重新命名與刪除。
10. 在生圖頁輸入圖片代號，確認該圖片覆蓋系統基準圖。
