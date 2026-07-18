@echo off
REM ============================================================
REM pre_commit.bat — VBSP-SCM Convention + Compile Check
REM Chạy trước mỗi commit để chặn lỗi cơ bản.
REM Cách dùng: pre_commit.bat                    (check toàn project)
REM            pre_commit.bat file1.py file2.py  (check file cụ thể)
REM Exit 0 = pass, 1 = có lỗi
REM ============================================================

setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1

set "ERR=0"
set "PYTHON_EXE="

REM Cho phép override khi Python của dự án nằm ở vị trí khác.
if defined VBSP_PYTHON call :try_python "%VBSP_PYTHON%"
if not defined PYTHON_EXE call :try_python "%~dp0venv\Scripts\python.exe"
if not defined PYTHON_EXE call :try_python "%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
    for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYTHON_EXE call :try_python "%%p"
)

if not defined PYTHON_EXE (
    echo ERROR: Khong tim thay Python chay duoc.
    echo        Kich hoat venv, cai Python vao PATH, hoac dat VBSP_PYTHON.
    exit /b 1
)

echo.
echo ============================================================
echo   VBSP-SCM Pre-Commit Check
echo   Python: %PYTHON_EXE%
echo ============================================================

REM --- 1. Convention check ---
echo.
echo [1/2] Convention check...
if "%~1"=="" (
    "%PYTHON_EXE%" scripts\check_conventions.py
    if errorlevel 1 set "ERR=1"
) else (
    call :convention_args %*
)

REM --- 2. Compile check ---
echo.
echo [2/2] Compile check...

if "%~1"=="" goto compile_all

:compile_args
if "%~1"=="" goto checks_done
if /i "%~x1"==".py" (
    call :compile_file "%~f1"
) else (
    echo   SKIP: %~1 ^(khong phai file .py^)
)
shift
goto compile_args

:compile_all
REM Check all Python files; loại các thư mục không thuộc mã nguồn active.
for /f "delims=" %%f in ('dir /s /b *.py 2^>nul ^| findstr /v "\tests\ \_archive\ \venv\ \.venv\ \node_modules\ \khtd-targets-app\ \backups\ \__pycache__\ check_conventions"') do call :compile_file "%%f"

:checks_done
echo.
if "%ERR%"=="0" (
    echo ============================================================
    echo   ALL CHECKS PASSED
    echo ============================================================
    exit /b 0
)

echo ============================================================
echo   SOME CHECKS FAILED - fix before commit!
echo ============================================================
exit /b 1

:try_python
if defined PYTHON_EXE exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=%~f1"
exit /b 0

:convention_args
if "%~1"=="" exit /b 0
if /i "%~x1"==".py" (
    "%PYTHON_EXE%" scripts\check_conventions.py "%~f1"
    if errorlevel 1 set "ERR=1"
) else (
    echo   SKIP: %~1 ^(khong phai file .py^)
)
shift
goto convention_args

:compile_file
if not exist "%~1" (
    echo   FAIL: %~1 ^(khong ton tai^)
    set "ERR=1"
    exit /b 0
)
"%PYTHON_EXE%" -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "%~1"
if errorlevel 1 (
    echo   FAIL: %~1
    set "ERR=1"
)
exit /b 0
