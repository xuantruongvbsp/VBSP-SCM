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

start /b "" ".\.venv\Scripts\streamlit.exe" run app.py --server.address 127.0.0.1 --server.port %PORT% --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false

echo Dang doi server khoi dong...
for /l %%i in (1,1,60) do (
  powershell -NoProfile -Command "exit ([int](-not (Test-NetConnection -ComputerName '127.0.0.1' -Port %PORT%).TcpTestSucceeded))" >nul 2>&1
  if not errorlevel 1 goto :OPEN_BROWSER
  timeout /t 1 /nobreak >nul
)

echo Khong the ket noi den %URL% sau 60 giay. Hay kiem tra cua so server.
pause
exit /b 1

:OPEN_BROWSER
start "" "%URL%"
echo Server dang chay tai %URL%
pause
