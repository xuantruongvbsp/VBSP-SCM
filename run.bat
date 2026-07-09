@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ============================================================
    echo   Chua cai dat moi truong!
    echo   Vui long chay setup_env.bat truoc.
    echo ============================================================
    pause
    exit /b 1
)

echo ============================================================
echo   VBSP-SCM — Dang khoi dong...
echo   Mo trinh duyet: http://localhost:8502
echo   Nhan Ctrl+C de dung.
echo ============================================================
echo.

start "" http://localhost:8502

venv\Scripts\streamlit run app.py --server.port 8502

pause
