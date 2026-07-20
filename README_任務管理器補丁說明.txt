Telemini 純文生圖任務管理器補丁

用途：
把純文生圖的主要流程集中到 services/image_task_manager.py，避免 Qwen 整理、OMI 送出、暫存等待、補考、取消分散在不同服務裡。

本次新增：
- telemini/services/image_task_manager.py

本次覆蓋：
- telemini/services/image_jobs.py
- telemini/services/qwen_service.py

目前接管範圍：
- 純文生圖
- Qwen prompt 整理
- Qwen 補考
- OMI 自架模型送出
- AI 匝道離線暫存等待
- 使用者取消
- OMI 圖片結果收尾

暫時保持原樣：
- 圖文生圖
- 整體圖生圖
- 遮罩局部修改
- 圖片庫
- Telegram 圖片保存

主要差異：
1. image_jobs.py 不再自己鋪完整純文生圖流程，只建立 ImageTaskContext 並交給 process_pure_text_omi_job。
2. image_task_manager.py 統一管理 prompting -> submitting -> queued/processing -> completed/canceled。
3. Qwen 等待本機 worker 時可接收 cancel_check；prompt生成中按取消不會再卡住。
4. prompt 整理失敗或 AI 匝道離線時，由任務管理器統一進入暫存/補考流程。
5. 上一版「原文需求硬保留」保留在 qwen_service.py 內。

套用：
1. 將 telemini 資料夾覆蓋到專案根目錄。
2. 重新部署 Render。
3. 重新啟動本機 OMI worker / AI 匝道。
4. 測試純文生圖：
   - 正常生成
   - prompt生成中取消
   - AI 匝道關閉後送任務，再開啟匝道

驗證：
已做 Python 語法檢查：
python3 -m py_compile services/image_task_manager.py services/image_jobs.py services/qwen_service.py

注意：
這版是第一階段任務管理器，先穩定純文生圖。其他生圖模式沒有被搬進任務管理器，避免改動過大。
