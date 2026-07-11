# 在 Telemini 專案根目錄執行。
$ErrorActionPreference = "SilentlyContinue"

Remove-Item -Recurse -Force ".agents", "_snapshot", "__pycache__"
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File -Filter "*.pyc" | Remove-Item -Force

Remove-Item -Force "api.py", "check_db.py", "test_db.py", "services/image_inpaint.py", "tools/python.txt"
Remove-Item -Recurse -Force "static/image_reference"

Get-ChildItem -File | Where-Object { $_.Name -like "*#U*" } | Remove-Item -Force
Get-ChildItem "docs" -File | Where-Object { $_.Name -like "*#U*" } | Remove-Item -Force

Write-Host "舊檔案清理完成"
