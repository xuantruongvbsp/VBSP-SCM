@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
set "ROOT=%~dp0"
rem Strip trailing backslash for clean path joins
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PORT=8502"
set "URL=http://localhost:%PORT%"
set "PY_EXE=%ROOT%\venv\Scripts\python.exe"
set "TMP_DIR=%ROOT%\tmp"
set "LOG_DIR=%ROOT%\logs"
set "LOCK_DIR=%TMP_DIR%\vbsp_launcher.lock"
set "PROBE_FILE=%TMP_DIR%\python_exec_check.txt"
set "VBSP_PROBE_FILE=%PROBE_FILE%"
set "LAUNCH_LOG=%LOG_DIR%\launcher_last.log"
set "SETUP_DONE_FILE=%TMP_DIR%\.vbsp_setup_done"
set "REQUIREMENTS_FILE=%ROOT%\requirements.txt"
set "LOG_RETENTION_DAYS=30"
set "JUST_INSTALLED=0"

rem Python 3.12 mac dinh; fallback path co dinh o buoc auto-detect
set "PY_CMD=py"
set "PY_ARGS=-3.12"

if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

if /I "%~1"=="--self-test" goto :self_test

rem Archive log cua lan chay truoc, sau do xoa log launcher qua han.
set "RUN_STAMP=%date%_%time%"
set "RUN_STAMP=%RUN_STAMP:/=-%"
set "RUN_STAMP=%RUN_STAMP:\=-%"
set "RUN_STAMP=%RUN_STAMP::=-%"
set "RUN_STAMP=%RUN_STAMP:.=-%"
set "RUN_STAMP=%RUN_STAMP:,=-%"
set "RUN_STAMP=%RUN_STAMP: =0%"
if exist "%LAUNCH_LOG%" (
    copy /y "%LAUNCH_LOG%" "%LOG_DIR%\launcher_%RUN_STAMP%.log" >nul 2>&1
)
forfiles /p "%LOG_DIR%" /m "launcher_*.log" /d -%LOG_RETENTION_DAYS% /c "cmd /c del /q @path" >nul 2>&1

echo [%date% %time%] START Chay_VBSP_SCM.bat > "%LAUNCH_LOG%"
echo CWD=%CD% >> "%LAUNCH_LOG%"

rem ============================================================================
rem  1. Lock check - tranh chay 2 lan
rem ============================================================================
if exist "%LOCK_DIR%" (
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo [%date% %time%] LOCK exists and port %PORT% is listening >> "%LAUNCH_LOG%"
        echo.
        echo App cu dang chay tren cong %PORT%.
        echo Dang tat app cu de khoi dong lai ban moi...
        echo.
        call :kill_port_processes
        if errorlevel 1 (
            echo   LOI: Port %PORT% khong thuoc VBSP-SCM, launcher se khong tu tat.
            echo   Hay dong ung dung dang chiem port hoac doi port cua ung dung do.
            goto :error_pause
        )
    )
    echo [%date% %time%] Remove stale launcher lock >> "%LAUNCH_LOG%"
    rmdir "%LOCK_DIR%" >nul 2>&1
)

mkdir "%LOCK_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] EXIT: launcher already running >> "%LAUNCH_LOG%"
    echo.
    echo VBSP-SCM dang co mot lan khoi dong khac dang chay.
    echo Neu vua bam nhieu lan, hay doi 10 giay.
    echo Neu van bi lap sau khi restart, xoa thu muc:
    echo %LOCK_DIR%
    echo.
    timeout /t 5 >nul
    exit /b 0
)

rem ============================================================================
rem  2. BANNER
rem ============================================================================
echo.
echo ============================================
echo   VBSP-SCM - He thong Tin dung Noi Bo
echo   NHCSXH Chi nhanh Dong Nai
echo ============================================
echo.

rem ============================================================================
rem  3. Port conflict check
rem ============================================================================
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [%date% %time%] PORT %PORT% already listening >> "%LAUNCH_LOG%"
    echo   Port %PORT% dang bi app cu chiem.
    echo   Dang tat app cu de khoi dong lai ban moi...
    echo.
    call :kill_port_processes
    if errorlevel 1 (
        echo   LOI: Port %PORT% khong thuoc VBSP-SCM, launcher se khong tu tat.
        echo   Hay dong ung dung dang chiem port hoac doi port cua ung dung do.
        goto :error_pause
    )
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo [%date% %time%] ERROR: port %PORT% still listening after taskkill >> "%LAUNCH_LOG%"
        echo   LOI: Khong tat duoc app cu dang chiem cong %PORT%.
        echo   Hay dong cua so Streamlit/CMD cu roi chay lai file nay.
        goto :error_pause
    )
    echo   Da tat app cu tren cong %PORT%.
    echo.
)

rem ============================================================================
rem  4. Auto-detect Python 3.12 + Auto-setup venv (neu can)
rem ============================================================================
set "NEED_SETUP=0"

rem 4a. Kiem tra venv da san sang chua
if exist "%PY_EXE%" (
    del "%PROBE_FILE%" >nul 2>&1
    "%PY_EXE%" -c "import os; from pathlib import Path; Path(os.environ['VBSP_PROBE_FILE']).write_text('ok', encoding='utf-8')" >> "%LAUNCH_LOG%" 2>&1
    if exist "%PROBE_FILE%" (
        set /p "PROBE_OK="<"%PROBE_FILE%"
        if "!PROBE_OK!"=="ok" (
            "%PY_EXE%" -c "import streamlit, pandas" >> "%LAUNCH_LOG%" 2>&1
            if !errorlevel! equ 0 goto :venv_ready
        )
    )
    echo [%date% %time%] venv exists but broken, will recreate >> "%LAUNCH_LOG%"
    set "NEED_SETUP=1"
) else (
    echo [%date% %time%] venv not found >> "%LAUNCH_LOG%"
    set "NEED_SETUP=1"
)

rem 4b. Neu can setup, tim Python 3.12
if not "!NEED_SETUP!"=="1" goto :venv_ready

echo.
echo -- Auto-setup: kiem tra Python 3.12... --
echo.

rem Thu py -3.12 truoc
"!PY_CMD!" !PY_ARGS! --version >nul 2>&1
if not errorlevel 1 goto :found_python

rem Thu cac duong dan co dinh
for %%p in ("%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "C:\Python312\python.exe" "C:\Program Files\Python312\python.exe") do (
    if exist "%%p" (
        "%%~p" --version >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=%%~p"
            set "PY_ARGS="
            goto :found_python
        )
    )
)

rem Khong tim thay
echo [%date% %time%] ERROR: Python 3.12 not found >> "%LAUNCH_LOG%"
echo.
echo ==============================================================
echo   KHONG TIM THAY Python 3.12
echo.
echo   Hay cai Python 3.12 tu:
echo   https://www.python.org/downloads/release/python-3129/
echo.
echo   LUU Y: Tick "Add Python to PATH" khi cai dat
echo   Sau khi cai, chay lai file nay.
echo ==============================================================
echo.
goto :error_pause

:found_python
for /f "tokens=2 delims= " %%v in ('"!PY_CMD!" !PY_ARGS! --version 2^>^&1') do set "PYVER=%%v"
echo   Tim thay: Python !PYVER! (!PY_CMD! !PY_ARGS!)
echo [%date% %time%] Found Python: !PY_CMD! !PY_ARGS! version !PYVER! >> "%LAUNCH_LOG%"

rem 4c. Tao/Xoa venv cu
if exist "%ROOT%\venv" (
    echo   Dang xoa venv cu...
    rmdir /s /q "%ROOT%\venv" >nul 2>&1
)
echo   Dang tao virtual environment...
"!PY_CMD!" !PY_ARGS! -m venv "%ROOT%\venv"
if errorlevel 1 (
    echo [%date% %time%] ERROR: venv creation failed >> "%LAUNCH_LOG%"
    echo   LOI: Khong the tao virtual environment.
    goto :error_pause
)

rem 4d. Cai packages
echo   Dang nang cap pip...
"%PY_EXE%" -m pip install --upgrade pip --quiet >> "%LAUNCH_LOG%" 2>&1

echo   Dang cai dat packages (co the mat 3-5 phut)...
echo   Vui long cho...
echo.
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [%date% %time%] ERROR: pip install failed >> "%LAUNCH_LOG%"
    echo   LOI: Cai dat packages that bai. Kiem tra ket noi Internet.
    goto :error_pause
)

rem Fix cac package thuong loi
"%PY_EXE%" -m pip install --force-reinstall protobuf python-dateutil --quiet >> "%LAUNCH_LOG%" 2>&1

rem 4e. Tao thu muc can thiet
if not exist "%ROOT%\cache" mkdir "%ROOT%\cache"
if not exist "%ROOT%\pgd_data" mkdir "%ROOT%\pgd_data"
if not exist "%ROOT%\backups" mkdir "%ROOT%\backups"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
if not exist "%ROOT%\tmp" mkdir "%ROOT%\tmp"

rem 4f. Verify import
"%PY_EXE%" -c "import streamlit, pandas, duckdb, pyarrow, plotly, openpyxl, docx, bcrypt" >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: module import failed after install >> "%LAUNCH_LOG%"
    echo   LOI: Mot so module khong import duoc. Hay chay setup_env.bat thu cong.
    goto :error_pause
)

echo   Setup hoan tat!
echo.
echo [%date% %time%] Auto-setup completed >> "%LAUNCH_LOG%"
set "JUST_INSTALLED=1"

:venv_ready
echo   Venv da san sang.

rem ============================================================================
rem  4g. Dong bo requirements khi file thay doi
rem ============================================================================
if "!JUST_INSTALLED!"=="1" (
    "%PY_EXE%" -m pip check >> "%LAUNCH_LOG%" 2>&1
    if errorlevel 1 (
        echo [%date% %time%] ERROR: pip check failed after setup >> "%LAUNCH_LOG%"
        echo   LOI: Dependency vua cai dat chua day du.
        goto :error_pause
    )
    call :write_setup_state
    if errorlevel 1 goto :error_pause
) else (
    call :sync_requirements
    if errorlevel 1 goto :error_pause
)

rem ============================================================================
rem  5. Kiem tra cac file/thu muc thiet yeu
rem ============================================================================
echo.
echo -- Kiem tra file cau hinh... --

set "MISSING_FILES="

if not exist "%ROOT%\credentials.json" (
    set "MISSING_FILES=%MISSING_FILES%  - credentials.json (Google Sheets/API)\n"
)
if not exist "%ROOT%\templates" (
    set "MISSING_FILES=%MISSING_FILES%  - templates/ (thu muc Word templates)\n"
)
if not exist "%ROOT%\pgd_data" (
    mkdir "%ROOT%\pgd_data" >nul 2>&1
)
if not exist "%ROOT%\backups" (
    mkdir "%ROOT%\backups" >nul 2>&1
)
if not exist "%ROOT%\cache" (
    mkdir "%ROOT%\cache" >nul 2>&1
)
if not exist "%ROOT%\logs" (
    mkdir "%ROOT%\logs" >nul 2>&1
)

if not "%MISSING_FILES%"=="" (
    echo.
    echo   CANH BAO: Thieu cac file/thu muc sau:
    echo %MISSING_FILES%
    echo   App van chay duoc nhung mot so tinh nang se bi han che.
    echo   - credentials.json: can cho Tien do nop BC (Google Sheets)
    echo   - templates/: can cho xuat Word/PDF
    echo.
) else (
    echo   Tat ca file cau hinh OK.
)

rem ============================================================================
rem  6. Verify imports
rem ============================================================================
echo.
echo -- Kiem tra thu vien... --
"%PY_EXE%" -c "import streamlit, pandas, dateutil" >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: core import failed >> "%LAUNCH_LOG%"
    echo   LOI: Khong import duoc streamlit/pandas/dateutil.
    echo   Hay chay setup_env.bat thu cong.
    goto :error_pause
)
echo   Streamlit + pandas OK.

rem ============================================================================
rem  7. Launch
rem ============================================================================
echo.
echo -- Khoi dong ung dung... --

rem Guard: verify python.exe exists
if not exist "%PY_EXE%" (
    echo [%date% %time%] ERROR: %PY_EXE% not found >> "%LAUNCH_LOG%"
    echo   LOI: Khong tim thay %PY_EXE%
    echo   Hay chay setup_env.bat thu cong de tao lai venv.
    goto :error_pause
)

echo.
echo   Streamlit se tu mo trinh duyet neu Windows cho phep.
echo   Neu trinh duyet khong tu mo, vao thu cong:
echo   %URL%
echo.
echo   De tat app: quay lai cua so nay va nhan Ctrl+C.
echo.
echo [%date% %time%] Start streamlit run >> "%LAUNCH_LOG%"

"%PY_EXE%" -m streamlit run app.py ^
  --server.port %PORT% ^
  --server.headless false ^
  --browser.gatherUsageStats false

set "APP_RC=%errorlevel%"
echo [%date% %time%] Streamlit exited rc=%APP_RC% >> "%LAUNCH_LOG%"
echo.
echo   Streamlit da dung voi ma: %APP_RC%
goto :error_pause

:success_pause
call :cleanup
pause
exit /b 0

:error_pause
call :cleanup
echo   Log kiem tra: %LAUNCH_LOG%
echo   Nhan phim bat ky de thoat.
pause
exit /b 1

:kill_port_processes
set "KILLED_PIDS="
set "KILL_FAILED=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    call :is_vbsp_process %%p
    if errorlevel 1 (
        echo [%date% %time%] REFUSE: PID %%p is not verified as VBSP-SCM >> "%LAUNCH_LOG%"
        echo   CANH BAO: PID %%p khong duoc xac minh la VBSP-SCM.
        set "KILL_FAILED=1"
    ) else (
        echo [%date% %time%] Stop verified VBSP-SCM on port %PORT%, PID %%p >> "%LAUNCH_LOG%"
        echo   Tat phien VBSP-SCM cu PID %%p...
        taskkill /F /PID %%p >nul 2>&1
        if errorlevel 1 (
            echo [%date% %time%] WARN: taskkill failed for PID %%p >> "%LAUNCH_LOG%"
            echo   CANH BAO: Khong tat duoc PID %%p.
            set "KILL_FAILED=1"
        ) else (
            set "KILLED_PIDS=!KILLED_PIDS! %%p"
        )
    )
)
if not "!KILLED_PIDS!"=="" timeout /t 2 >nul
if "!KILL_FAILED!"=="1" (
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 exit /b 1
)
exit /b 0

:is_vbsp_process
set "CHECK_PID=%~1"
set "PID_INFO_FILE=%TMP_DIR%\vbsp_pid_%CHECK_PID%.txt"
set "IS_VBSP_PROCESS=1"
del "%PID_INFO_FILE%" >nul 2>&1

rem PowerShell chay dong bo trong cung console, chi doc metadata process.
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=%CHECK_PID%' -ErrorAction SilentlyContinue; if ($null -ne $p) { Write-Output $p.ExecutablePath; Write-Output $p.CommandLine }" > "%PID_INFO_FILE%" 2>nul
if not exist "%PID_INFO_FILE%" exit /b 1
for %%z in ("%PID_INFO_FILE%") do if %%~zz EQU 0 set "IS_VBSP_PROCESS=0"

findstr /I /L /C:"%PY_EXE%" "%PID_INFO_FILE%" >nul 2>&1
if errorlevel 1 set "IS_VBSP_PROCESS=0"
findstr /I /L /C:"streamlit" "%PID_INFO_FILE%" >nul 2>&1
if errorlevel 1 set "IS_VBSP_PROCESS=0"
findstr /I /L /C:"app.py" "%PID_INFO_FILE%" >nul 2>&1
if errorlevel 1 set "IS_VBSP_PROCESS=0"

del "%PID_INFO_FILE%" >nul 2>&1
if "%IS_VBSP_PROCESS%"=="1" exit /b 0
exit /b 1

:calculate_requirements_hash
set "REQ_HASH="
set "REQ_HASH_FILE=%TMP_DIR%\requirements_hash.txt"
if not exist "%REQUIREMENTS_FILE%" (
    echo [%date% %time%] ERROR: requirements.txt not found >> "%LAUNCH_LOG%"
    echo   LOI: Khong tim thay %REQUIREMENTS_FILE%
    exit /b 1
)
del "%REQ_HASH_FILE%" >nul 2>&1
set "VBSP_REQUIREMENTS_FILE=%REQUIREMENTS_FILE%"
set "VBSP_REQUIREMENTS_HASH_FILE=%REQ_HASH_FILE%"
"%PY_EXE%" -c "import hashlib, os; from pathlib import Path; src=Path(os.environ['VBSP_REQUIREMENTS_FILE']); dst=Path(os.environ['VBSP_REQUIREMENTS_HASH_FILE']); dst.write_text(hashlib.sha256(src.read_bytes()).hexdigest(), encoding='ascii')" >nul 2>&1
if exist "%REQ_HASH_FILE%" set /p "REQ_HASH="<"%REQ_HASH_FILE%"
del "%REQ_HASH_FILE%" >nul 2>&1
if not defined REQ_HASH (
    echo [%date% %time%] ERROR: cannot hash requirements.txt >> "%LAUNCH_LOG%"
    echo   LOI: Khong the kiem tra thay doi requirements.txt.
    exit /b 1
)
exit /b 0

:write_setup_state
call :calculate_requirements_hash
if errorlevel 1 exit /b 1
> "%SETUP_DONE_FILE%" echo %REQ_HASH%
echo [%date% %time%] Saved requirements hash %REQ_HASH% >> "%LAUNCH_LOG%"
exit /b 0

:sync_requirements
call :calculate_requirements_hash
if errorlevel 1 exit /b 1

set "SAVED_REQ_HASH="
if exist "%SETUP_DONE_FILE%" set /p "SAVED_REQ_HASH="<"%SETUP_DONE_FILE%"
if /I "%REQ_HASH%"=="%SAVED_REQ_HASH%" (
    echo [%date% %time%] requirements.txt unchanged >> "%LAUNCH_LOG%"
    exit /b 0
)

echo.
echo -- requirements.txt da thay doi, dang dong bo thu vien... --
echo   Chi chay khi requirements thay doi hoac lan dau nang cap launcher.
echo [%date% %time%] requirements hash changed: %SAVED_REQ_HASH% to %REQ_HASH% >> "%LAUNCH_LOG%"
"%PY_EXE%" -m pip install -r "%REQUIREMENTS_FILE%" >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: dependency sync failed >> "%LAUNCH_LOG%"
    echo   LOI: Dong bo dependency that bai. Xem log: %LAUNCH_LOG%
    exit /b 1
)
"%PY_EXE%" -m pip check >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: pip check failed after dependency sync >> "%LAUNCH_LOG%"
    echo   LOI: Dependency bi xung dot. Xem log: %LAUNCH_LOG%
    exit /b 1
)
> "%SETUP_DONE_FILE%" echo %REQ_HASH%
echo [%date% %time%] Dependency sync completed >> "%LAUNCH_LOG%"
echo   Dong bo dependency hoan tat.
exit /b 0

:self_test
call :calculate_requirements_hash
if errorlevel 1 (
    echo LAUNCHER SELF-TEST FAILED: requirements hash
    exit /b 1
)
call :is_vbsp_process 0
if not errorlevel 1 (
    echo LAUNCHER SELF-TEST FAILED: PID ownership guard
    exit /b 1
)
echo LAUNCHER SELF-TEST OK
exit /b 0

:cleanup
rmdir "%LOCK_DIR%" >nul 2>&1
exit /b 0
