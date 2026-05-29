@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"
set "PORT=8501"
set "URL=http://localhost:%PORT%"
set "VENV=venv"
set "PY_EXE=%VENV%\Scripts\python.exe"

:: ─── Bước 1: Kiểm tra venv ──────────────────────────────────────
echo.
echo ============================================
echo   VBSP-SCM — He thong Tin dung Noi bo
echo ============================================
echo.
echo [1/3] Kiem tra moi truong ao (venv)...

if not exist "%PY_EXE%" (
    echo   Chua cai dat! Dang chay setup_env.bat...
    echo.
    call "%~dp0setup_env.bat"
    if !errorlevel! neq 0 (
        echo   LOI: Cai dat that bai.
        pause
        exit /b 1
    )
    echo.
    echo   Quay lai binh thuong...
    echo.
) else (
    echo   Venv da san sang.
)

:: ─── Bước 2: Kiểm tra thư viện ──────────────────────────────────
echo.
echo [2/3] Kiem tra thu vien...
"%PY_EXE%" -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo   Chua cai dat! Dang chay setup_env.bat...
    echo.
    call "%~dp0setup_env.bat"
    if !errorlevel! neq 0 (
        echo   LOI: Cai dat that bai.
        pause
        exit /b 1
    )
) else (
    echo   Thu vien OK.
)

:: ─── Bước 3: Khởi động ──────────────────────────────────────────
echo.
echo [3/3] Khoi dong ung dung...
echo.
echo   URL: %URL%
echo   Tat: Nhan Ctrl+C
echo.

start "" %URL%

"%PY_EXE%" -m streamlit run app.py ^
  --server.port %PORT% ^
  --browser.gatherUsageStats false

if %errorlevel% neq 0 (
    echo.
    echo   Ung dung da dung. Nhan phim bat ky de thoat.
    pause
)
