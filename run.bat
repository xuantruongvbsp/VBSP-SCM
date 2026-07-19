@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "PORT=8502"
set "URL=http://localhost:%PORT%"
set "PY_EXE=venv\Scripts\python.exe"
set "PROBE_FILE=%CD%\tmp\python_exec_check.txt"
set "VBSP_PROBE_FILE=%PROBE_FILE%"

if not exist "%PY_EXE%" (
    echo ============================================================
    echo   Khong tim thay %PY_EXE%.
    echo   Hay chay setup_env.bat truoc.
    echo ============================================================
    pause
    exit /b 1
)

if not exist "tmp" mkdir tmp >nul 2>&1
del "%PROBE_FILE%" >nul 2>&1
"%PY_EXE%" -c "import os; from pathlib import Path; Path(os.environ['VBSP_PROBE_FILE']).write_text('ok', encoding='utf-8')"
if not exist "%PROBE_FILE%" (
    echo ============================================================
    echo   Python trong venv khong thuc thi duoc lenh kiem tra.
    echo   Khuyen nghi: cai Python 3.12, sau do chay setup_env.bat.
    echo ============================================================
    pause
    exit /b 1
)

echo ============================================================
echo   VBSP-SCM - Dang khoi dong
echo   Streamlit se tu mo trinh duyet neu Windows cho phep.
echo   Neu trinh duyet khong tu mo, vao:
echo   %URL%
echo   Nhan Ctrl+C de dung.
echo ============================================================
echo.

"%PY_EXE%" -m streamlit run app.py ^
  --server.port %PORT% ^
  --server.headless false ^
  --browser.gatherUsageStats false

set "APP_RC=%errorlevel%"
echo.
echo   Streamlit da dung voi ma: %APP_RC%
pause
exit /b %APP_RC%
