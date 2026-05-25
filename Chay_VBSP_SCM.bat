@echo off
setlocal

cd /d %~dp0
set "PORT=8501"
set "URL=http://127.0.0.1:%PORT%"

if not exist ".\.venv\Scripts\streamlit.exe" (
  echo Khong tim thay .venv\Scripts\streamlit.exe
  echo Hay tao venv va cai requirements.txt truoc.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   VBSP-SCM — He thong Tin dung Noi bo
echo ============================================
echo.
echo   URL: %URL%
echo   Auto-reload: Co (watchdog .py)
echo   Dung: Nhan Ctrl+C
echo.
echo Dang khoi dong server...

".\.venv\Scripts\streamlit.exe" run app.py ^
  --server.address 127.0.0.1 ^
  --server.port %PORT% ^
  --server.headless false ^
  --browser.gatherUsageStats false
