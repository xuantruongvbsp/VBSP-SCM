@echo off
setlocal enabledelayedexpansion

cd /d %~dp0
set "PORT=8501"
set "URL=http://127.0.0.1:%PORT%"
set "PYTHON_CMD="

:: ─── Bước 1: Tìm Python ─────────────────────────────────────────
echo.
echo ============================================
echo   VBSP-SCM — He thong Tin dung Noi bo
echo ============================================
echo.
echo [1/4] Dang tim Python...

:: Thử python trực tiếp
python --version >nul 2>&1
if %errorlevel% equ 0 (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "delims=" %%i in ('where python') do set "PYTHON_CMD=%%i"
        goto :found_python
    )
)

:: Thử python trong LocalAppData (cài từ python.org)
for /d %%p in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%p\python.exe" (
        set "PYTHON_CMD=%%p\python.exe"
        goto :found_python
    )
)

:: Thử python trong Program Files
for /d %%p in ("C:\Program Files\Python*") do (
    if exist "%%p\python.exe" (
        set "PYTHON_CMD=%%p\python.exe"
        goto :found_python
    )
)

echo Khong tim thay Python. Hay tai va cai dat tu: https://www.python.org/downloads/
echo Nho tick chon "Add Python to PATH" khi cai dat.
pause
exit /b 1

:found_python
echo   Tim thay: !PYTHON_CMD!
!PYTHON_CMD! --version

:: ─── Bước 2: Tạo venv nếu chưa có ────────────────────────────────
echo.
echo [2/4] Kiem tra moi truong ao (venv)...

if not exist ".venv\Scripts\python.exe" (
    echo   Dang tao venv...
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo   LOI: Khong the tao venv.
        pause
        exit /b 1
    )
    echo   Da tao venx thanh cong.
) else (
    echo   Venv da ton tai.
)

:: ─── Bước 3: Cài thư viện nếu chưa đủ ────────────────────────────
echo.
echo [3/4] Kiem tra thu vien...

if not exist ".venv\Scripts\streamlit.exe" (
    echo   Dang cai dat thu vien (lan dau, co the mat 2-5 phut)...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    ".venv\Scripts\python.exe" -m pip install reportlab kaleido
    if !errorlevel! neq 0 (
        echo   LOI: Khong the cai thu vien. Vui long thu lai.
        pause
        exit /b 1
    )
    echo   Da cai dat thu vien thanh cong.
) else (
    echo   Thu vien da san sang.
)

:: ─── Bước 4: Chạy ứng dụng ───────────────────────────────────────
echo.
echo [4/4] Khoi dong ung dung...
echo.
echo   URL: %URL%
echo   Auto-reload: Co (theo doi file .py)
echo   Tat: Nhan Ctrl+C
echo.

".venv\Scripts\streamlit.exe" run app.py ^
  --server.address 127.0.0.1 ^
  --server.port %PORT% ^
  --server.headless false ^
  --browser.gatherUsageStats false

if %errorlevel% neq 0 (
    echo.
    echo Ung dung da dung voi ma loi: %errorlevel%
    pause
)
