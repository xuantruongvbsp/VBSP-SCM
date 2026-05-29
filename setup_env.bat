@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   VBSP-SCM — Cai dat moi truong 1 lan duy nhat
echo   He thong Quan tri Tin dung Noi bo NHCSXH CN Dong Nai
echo ============================================================
echo.

cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV=%ROOT%venv"

:: =============================================================
:: Buoc 0: Kiem tra Python
:: =============================================================
echo [0/6] Kiem tra Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong tim thay Python!
    echo        Vui long cai Python 3.10+ tu https://python.org
    echo        Tich chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        Python %PYVER% — OK
echo.

:: =============================================================
:: Buoc 1: Dong bo thoi gian he thong (quan trong cho GSheet)
:: =============================================================
echo [1/6] Dong bo thoi gian...
net start w32time >nul 2>&1
w32tm /resync /force >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo        OK — da dong bo voi time.windows.com
) else (
    echo        Canh bao: Khong dong bo duoc thoi gian.
    echo        Anh huong: Google Sheets co the bao loi JWT.
    echo        Khac phuc: Vao Settings ^> Time ^> Sync ngay
)
echo.

:: =============================================================
:: Buoc 2: Tao virtual environment (xoa cu neu co)
:: =============================================================
echo [2/6] Tao virtual environment...
if exist "%VENV%" (
    echo        Dang xoa venv cu...
    rmdir /s /q "%VENV%" 2>nul
)
python -m venv "%VENV%"
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the tao virtual environment!
    pause
    exit /b 1
)
echo        OK — da tao venv\
echo.

:: =============================================================
:: Buoc 3: Nang cap pip
:: =============================================================
echo [3/6] Nang cap pip...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo        OK
echo.

:: =============================================================
:: Buoc 4: Cai dat tat ca packages
:: =============================================================
echo [4/6] Cai dat packages tu requirements.txt...
echo        (co the mat 3-5 phut, vui long cho...)
echo.
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Cai dat packages that bai!
    echo        Kiem tra ket noi internet va thu lai.
    pause
    exit /b 1
)
echo.
echo        OK — da cai dat tat ca packages
echo.

:: =============================================================
:: Buoc 5: Tao cac thu muc can thiet
:: =============================================================
echo [5/6] Tao thu muc...
if not exist "cache"    (mkdir cache    && echo        Tao cache/)    else (echo        cache/    — da co)
if not exist "pgd_data" (mkdir pgd_data && echo        Tao pgd_data/) else (echo        pgd_data/ — da co)
if not exist "backups"  (mkdir backups  && echo        Tao backups/)  else (echo        backups/  — da co)
echo.

:: =============================================================
:: Buoc 6: Kiem tra nhanh — import cac module chinh
:: =============================================================
echo [6/6] Kiem tra...
set "FAIL="
"%VENV%\Scripts\python.exe" -c "import streamlit" 2>nul || set "FAIL=streamlit"
"%VENV%\Scripts\python.exe" -c "import pandas"     2>nul || set "FAIL=!FAIL! pandas"
"%VENV%\Scripts\python.exe" -c "import duckdb"      2>nul || set "FAIL=!FAIL! duckdb"
"%VENV%\Scripts\python.exe" -c "import pyarrow"     2>nul || set "FAIL=!FAIL! pyarrow"
"%VENV%\Scripts\python.exe" -c "import plotly"      2>nul || set "FAIL=!FAIL! plotly"
"%VENV%\Scripts\python.exe" -c "import openpyxl"    2>nul || set "FAIL=!FAIL! openpyxl"
"%VENV%\Scripts\python.exe" -c "import docx"        2>nul || set "FAIL=!FAIL! python-docx"
"%VENV%\Scripts\python.exe" -c "import bcrypt"      2>nul || set "FAIL=!FAIL! bcrypt"

if "!FAIL!" NEQ "" (
    echo [LOI] Thieu module: !FAIL!
    echo        Vui long chay lai setup_env.bat
    pause
    exit /b 1
)

"%VENV%\Scripts\python.exe" -c "import py_compile; py_compile.compile('app.py', doraise=True)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Bien dich app.py that bai!
    pause
    exit /b 1
)
echo        Tat ca modules OK + app.py compile OK
echo.

:: =============================================================
:: HOAN TAT
:: =============================================================
echo ============================================================
echo   HOAN TAT! Moi truong da san sang.
echo.
echo   De chay ung dung, double-click vao file:
echo       run.bat
echo.
echo   Hoac chay bang tay:
echo       venv\Scripts\streamlit run app.py
echo ============================================================
echo.
pause
