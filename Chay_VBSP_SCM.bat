@echo off
setlocal

cd /d %~dp0
echo Dang khoi dong VBSP-SCM...
set "PORT=8501"
set "URL=http://127.0.0.1:%PORT%"

if not exist ".\.venv\Scripts\streamlit.exe" (
  echo Khong tim thay .venv\Scripts\streamlit.exe
  echo Hay tao venv va cai requirements.txt truoc.
  pause
  exit /b 1
)

start /b "" ".\.venv\Scripts\streamlit.exe" run app.py ^
  --server.address 127.0.0.1 ^
  --server.port %PORT% ^
  --server.headless true ^
  --browser.gatherUsageStats false

echo Server dang khoi dong, cho 3 giay...
timeout /t 3 /nobreak >nul

start "" "%URL%"
echo Server dang chay tai %URL%
echo Auto-reload khi save file .py (watchdog). Giu cua so nay de server tiep tuc chay.
echo Nhan Ctrl+C de dung server.
