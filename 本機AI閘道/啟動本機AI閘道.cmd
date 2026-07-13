@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "閘道設定.cmd" (
  echo 找不到「閘道設定.cmd」
  echo 請先複製「閘道設定範例.cmd」並改名為「閘道設定.cmd」
  pause
  exit /b 1
)
call "閘道設定.cmd"
python app.py
if errorlevel 1 py -3 app.py
pause
