# 圖片解析模型 fallback 更新

## 更新目標

圖片、靜態貼圖解析改成：

1. 優先送進 `gemini-3.5-flash`
2. 如果主模型遇到 quota / rate limit / 服務暫時不可用，改送進 `gemini-3-flash-preview`
3. 主模型出現 429 / RESOURCE_EXHAUSTED / 503 後，會在目前 Render process 內暫停嘗試到 Pacific time 下一次午夜重置後
4. 避免每天額度達上限後，每張圖片都先撞一次 3.5 Flash

## 修改檔案

- `config.py`
- `services/gemini_service.py`

## 環境變數

可以在 Render 設定：

```text
GEMINI_VISION_MODEL=gemini-3.5-flash
GEMINI_VISION_FALLBACK_MODEL=gemini-3-flash-preview
```

如果 Render 已經有舊的：

```text
GEMINI_VISION_MODEL=gemini-2.5-flash
```

要刪掉或改成：

```text
GEMINI_VISION_MODEL=gemini-3.5-flash
```

## Render log 判讀

成功：

```text
GEMINI IMAGE TO TEXT OK model=gemini-3.5-flash len=...
```

主模型達上限後切換：

```text
GEMINI IMAGE TO TEXT ERROR model=gemini-3.5-flash ... 429 RESOURCE_EXHAUSTED ...
GEMINI IMAGE MODEL DISABLED UNTIL RESET model=gemini-3.5-flash ...
GEMINI IMAGE TO TEXT OK model=gemini-3-flash-preview len=...
```

全部失敗：

```text
GEMINI IMAGE TO TEXT FAILED all_models=[...]
```
