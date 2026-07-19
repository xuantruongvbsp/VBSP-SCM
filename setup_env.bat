@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV=%ROOT%venv"
set "TMP_DIR=%ROOT%tmp"
set "PY_PROBE=%TMP_DIR%\setup_python_probe.txt"
set "PY_CMD=py -3.12"
set "PY312_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

echo.
echo ============================================================
echo   VBSP-SCM - Cai dat moi truong 1 lan duy nhat
echo   He thong Quan tri Tin dung Noi bo NHCSXH CN Dong Nai
echo ============================================================
echo.

echo [0/6] Kiem tra Python 3.12...
%PY_CMD% --version >nul 2>&1
if errorlevel 1 (
    if exist "%PY312_EXE%" (
        set "PY_CMD=%PY312_EXE%"
    ) else (
        goto :no_python312
    )
)

if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1
del "%PY_PROBE%" >nul 2>&1
set "VBSP_SETUP_PY_PROBE=%PY_PROBE%"
%PY_CMD% -c "import os, sys; from pathlib import Path; Path(os.environ['VBSP_SETUP_PY_PROBE']).write_text(str(sys.version_info[0])+'.'+str(sys.version_info[1]), encoding='utf-8')" >nul 2>&1
if not exist "%PY_PROBE%" goto :python_probe_failed

set /p "PYVER_SHORT="<"%PY_PROBE%"
if not "%PYVER_SHORT%"=="3.12" goto :wrong_python

for /f "tokens=2 delims= " %%v in ('%PY_CMD% --version 2^>^&1') do set "PYVER=%%v"
echo        Python %PYVER% - OK
echo.

echo [1/6] Dong bo thoi gian...
net start w32time >nul 2>&1
w32tm /resync /force >nul 2>&1
if errorlevel 1 (
    echo        Canh bao: Khong dong bo duoc thoi gian.
    echo        Neu Google Sheets bao loi JWT, vao Settings ^> Time ^> Sync now.
) else (
    echo        OK - da dong bo thoi gian.
)
echo.

echo [2/6] Tao virtual environment...
if exist "%VENV%" (
    echo        Dang xoa venv cu...
    rmdir /s /q "%VENV%" 2>nul
)
%PY_CMD% -m venv "%VENV%"
if errorlevel 1 goto :venv_failed
echo        OK - da tao venv
echo.

echo [3/6] Nang cap pip...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
if errorlevel 1 goto :pip_failed
echo        OK
echo.

echo [4/6] Cai dat packages tu requirements.txt...
echo        Co the mat 3-5 phut, vui long cho...
echo.
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :packages_failed
echo.
echo        Sua loi package cai thieu file neu pip cache bi loi...
"%VENV%\Scripts\python.exe" -m pip install --force-reinstall protobuf python-dateutil
if errorlevel 1 goto :packages_failed
echo.
echo        OK - da cai dat packages
echo.

echo [5/6] Tao thu muc...
if not exist "cache" mkdir cache
if not exist "pgd_data" mkdir pgd_data
if not exist "backups" mkdir backups
if not exist "logs" mkdir logs
if not exist "tmp" mkdir tmp
echo        OK
echo.

echo [6/6] Kiem tra nhanh...
set "FAIL="
"%VENV%\Scripts\python.exe" -c "import streamlit" 2>nul || set "FAIL=%FAIL% streamlit"
"%VENV%\Scripts\python.exe" -c "import pandas" 2>nul || set "FAIL=%FAIL% pandas"
"%VENV%\Scripts\python.exe" -c "import dateutil" 2>nul || set "FAIL=%FAIL% python-dateutil"
"%VENV%\Scripts\python.exe" -c "import duckdb" 2>nul || set "FAIL=%FAIL% duckdb"
"%VENV%\Scripts\python.exe" -c "import pyarrow" 2>nul || set "FAIL=%FAIL% pyarrow"
"%VENV%\Scripts\python.exe" -c "import plotly" 2>nul || set "FAIL=%FAIL% plotly"
"%VENV%\Scripts\python.exe" -c "import openpyxl" 2>nul || set "FAIL=%FAIL% openpyxl"
"%VENV%\Scripts\python.exe" -c "import docx" 2>nul || set "FAIL=%FAIL% python-docx"
"%VENV%\Scripts\python.exe" -c "import bcrypt" 2>nul || set "FAIL=%FAIL% bcrypt"
if not "%FAIL%"=="" goto :module_failed

"%VENV%\Scripts\python.exe" -m pip check
if errorlevel 1 goto :pip_check_failed

"%VENV%\Scripts\python.exe" -c "import py_compile; py_compile.compile('app.py', doraise=True)" 2>nul
if errorlevel 1 goto :compile_failed
echo        Tat ca modules OK + app.py compile OK
echo.

echo ============================================================
echo   HOAN TAT. Moi truong da san sang.
echo.
echo   De chay ung dung:
echo       Chay_VBSP_SCM.bat
echo.
echo   URL:
echo       http://localhost:8502
echo ============================================================
echo.
pause
exit /b 0

:no_python312
echo [LOI] Khong tim thay Python 3.12 qua lenh: %PY_CMD%
echo        Hay cai Python 3.12 tu https://python.org
echo        Nho tick "Add Python to PATH" khi cai dat.
echo        Sau do mo CMD moi va kiem tra: py -3.12 --version
pause
exit /b 1

:python_probe_failed
echo [LOI] Python 3.12 tim thay nhung khong thuc thi duoc lenh kiem tra.
echo        Hay mo CMD moi va chay: py -3.12 --version
pause
exit /b 1

:wrong_python
echo [LOI] Lenh %PY_CMD% dang tra ve Python %PYVER_SHORT%, khong phai 3.12.
echo        Hay cai lai Python 3.12 va chay lai setup_env.bat.
pause
exit /b 1

:venv_failed
echo [LOI] Khong the tao virtual environment.
pause
exit /b 1

:pip_failed
echo [LOI] Nang cap pip that bai.
pause
exit /b 1

:packages_failed
echo [LOI] Cai dat packages that bai.
echo        Kiem tra ket noi internet va chay lai setup_env.bat.
pause
exit /b 1

:module_failed
echo [LOI] Thieu module:%FAIL%
echo        Hay chay lai setup_env.bat.
pause
exit /b 1

:pip_check_failed
echo [LOI] pip check phat hien dependency bi thieu hoac hong.
echo        Hay chay lai setup_env.bat. Neu van loi, xoa venv va chay lai.
pause
exit /b 1

:compile_failed
echo [LOI] Bien dich app.py that bai.
pause
exit /b 1
