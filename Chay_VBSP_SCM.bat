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
set "APP_PID_FILE=%TMP_DIR%\vbsp_streamlit.pid"
set "LOG_DIR=%ROOT%\logs"
set "LOCK_DIR=%TMP_DIR%\vbsp_launcher.lock"
set "PROBE_FILE=%TMP_DIR%\python_exec_check.txt"
set "VBSP_PROBE_FILE=%PROBE_FILE%"
set "LAUNCH_LOG=%LOG_DIR%\launcher_last.log"
set "SETUP_DONE_FILE=%TMP_DIR%\.vbsp_setup_done"
set "REQUIREMENTS_FILE=%ROOT%\requirements.txt"
set "REQUIREMENTS_LOCK_FILE=%ROOT%\requirements.lock.txt"
set "PIP_VERSION=26.1.2"
set "LOG_RETENTION_DAYS=30"
set "JUST_INSTALLED=0"
set "HEADLESS=false"
set "FORCE_KILL=false"
set "ALT_PORT=8503"

rem Python 3.12 mac dinh; fallback path co dinh o buoc auto-detect
set "PY_CMD=py"
set "PY_ARGS=-3.12"

if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

rem Parse flags loop
:parse_flags
if "%~1"=="" goto :flags_done
if /I "%~1"=="--self-test" goto :self_test
if /I "%~1"=="--no-browser" (
    set "HEADLESS=true"
    shift
    goto :parse_flags
)
if /I "%~1"=="--force-kill" (
    set "FORCE_KILL=true"
    shift
    goto :parse_flags
)
if /I "%~1"=="--port" (
    set "PORT=%~2"
    set "URL=http://localhost:%~2"
    shift
    shift
    goto :parse_flags
)
shift
goto :parse_flags
:flags_done

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
call :cleanup_stale_pid_marker

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
            call :prompt_alt_port_or_exit
            if errorlevel 1 goto :error_pause
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
echo   Chi nhanh Ngan hang Chinh sach xa hoi thanh pho Dong Nai
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
        call :prompt_alt_port_or_exit
        if errorlevel 1 goto :error_pause
    )
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo [%date% %time%] WARN: port %PORT% still listening, try alt port >> "%LAUNCH_LOG%"
        call :prompt_alt_port_or_exit
        if errorlevel 1 (
            echo   LOI: Khong tat duoc app cu dang chiem cong %PORT%.
            echo   Hay dong cua so Streamlit/CMD cu roi chay lai file nay.
            goto :error_pause
        )
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

rem 4c. Kiem tra lockfile truoc khi tao/xoa venv
if not exist "%REQUIREMENTS_LOCK_FILE%" (
    echo [%date% %time%] ERROR: requirements.lock.txt not found >> "%LAUNCH_LOG%"
    echo   LOI: Khong tim thay %REQUIREMENTS_LOCK_FILE%
    goto :error_pause
)
"!PY_CMD!" !PY_ARGS! "%ROOT%\scripts\validate_dependency_lock.py" "%REQUIREMENTS_FILE%" "%REQUIREMENTS_LOCK_FILE%" >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: dependency lock is inconsistent >> "%LAUNCH_LOG%"
    echo   LOI: requirements.txt va requirements.lock.txt khong dong bo.
    echo   Hay tao lai lockfile truoc khi tao lai venv.
    goto :error_pause
)

rem 4d. Tao/Xoa venv cu
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

rem 4e. Cai packages tu lockfile
echo   Dang cai pip %PIP_VERSION%...
"%PY_EXE%" -m pip install "pip==%PIP_VERSION%" --quiet >> "%LAUNCH_LOG%" 2>&1

echo   Dang cai dat packages (co the mat 3-5 phut)...
echo   Vui long cho...
echo.
"%PY_EXE%" -m pip install --no-deps -r "%REQUIREMENTS_LOCK_FILE%"
if errorlevel 1 (
    echo [%date% %time%] ERROR: pip install failed >> "%LAUNCH_LOG%"
    echo   LOI: Cai dat packages that bai. Kiem tra ket noi Internet.
    goto :error_pause
)

rem 4f. Tao thu muc can thiet
if not exist "%ROOT%\cache" mkdir "%ROOT%\cache"
if not exist "%ROOT%\pgd_data" mkdir "%ROOT%\pgd_data"
if not exist "%ROOT%\backups" mkdir "%ROOT%\backups"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
if not exist "%ROOT%\tmp" mkdir "%ROOT%\tmp"

rem 4g. Verify import
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
rem  4h. Dong bo requirements/lockfile khi file thay doi
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

rem KHONG dung dau ngoac () trong noi dung thong bao - lam vo cu phap if (...) cua CMD.
if not exist "%ROOT%\credentials.json" (
    set "MISSING_FILES=%MISSING_FILES%  - credentials.json [Google Sheets/API]\n"
)
if not exist "%ROOT%\templates" (
    set "MISSING_FILES=%MISSING_FILES%  - templates/ [thu muc Word templates]\n"
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
    echo   - credentials.json: can cho Tien do nop BC [Google Sheets]
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
if /I "%HEADLESS%"=="true" (
    echo   Che do DEV: Streamlit khong tu mo them tab trinh duyet.
    echo   Giu nguyen tab Chrome hien co, hoac mo thu cong:
    echo   %URL%
) else (
    echo   Streamlit se tu mo trinh duyet neu Windows cho phep.
    echo   Neu trinh duyet khong tu mo, vao thu cong:
    echo   %URL%
)
echo.
echo   De tat app: quay lai cua so nay va nhan Ctrl+C.
echo.
echo [%date% %time%] Start streamlit run >> "%LAUNCH_LOG%"

"%PY_EXE%" -m streamlit run app.py ^
  --server.port %PORT% ^
  --server.headless %HEADLESS% ^
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
set "SEEN_PIDS="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    call :register_pid_once %%p
    if not errorlevel 1 call :handle_port_pid %%p
)
if not "!KILLED_PIDS!"=="" timeout /t 2 >nul
if "!KILL_FAILED!"=="1" (
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 exit /b 1
)
exit /b 0

:register_pid_once
for %%s in (!SEEN_PIDS!) do if "%%s"=="%~1" exit /b 1
set "SEEN_PIDS=!SEEN_PIDS! %~1"
exit /b 0

:handle_port_pid
set "PORT_PID=%~1"
call :classify_pid_tier %PORT_PID%
set "PID_TIER=%errorlevel%"

echo [%date% %time%] PID %PORT_PID% classified as tier %PID_TIER% >> "%LAUNCH_LOG%"

if "%PID_TIER%"=="0" goto :kill_silent_tier0
if "%PID_TIER%"=="1" goto :handle_tier1
if "%PID_TIER%"=="2" goto :handle_tier2
if "%PID_TIER%"=="3" goto :handle_tier3
goto :handle_tier3

:kill_silent_tier0
echo [%date% %time%] Stop verified VBSP-SCM on port %PORT%, PID %PORT_PID% (tier 0) >> "%LAUNCH_LOG%"
echo   Tat phien VBSP-SCM cu PID %PORT_PID%...
goto :do_kill

:handle_tier1
echo   CANH BAO: PID %PORT_PID% xac dinh la Python co dau hieu VBSP-SCM.
call :show_process_info %PORT_PID%
if /I "%FORCE_KILL%"=="true" goto :kill_silent_tier2
call :prompt_user_kill Y 12 %PORT_PID% Tier-1
if errorlevel 1 (
    echo [%date% %time%] User skipped kill PID %PORT_PID% >> "%LAUNCH_LOG%"
    set "KILL_FAILED=1"
    exit /b 0
)
goto :do_kill

:handle_tier2
echo   CANH BAO: PID %PORT_PID% la tien trinh Python khong xac minh ro.
call :show_process_info %PORT_PID%
if /I "%FORCE_KILL%"=="true" goto :kill_silent_tier2
call :prompt_user_kill Y 12 %PORT_PID% Tier-2
if errorlevel 1 (
    echo [%date% %time%] User skipped kill PID %PORT_PID% >> "%LAUNCH_LOG%"
    set "KILL_FAILED=1"
    exit /b 0
)
goto :do_kill

:kill_silent_tier2
echo [%date% %time%] Force-kill Python PID %PORT_PID% (--force-kill on) >> "%LAUNCH_LOG%"
echo   Tu dong tat PID %PORT_PID% vi --force-kill...
goto :do_kill

:handle_tier3
echo.
echo   ========================================
echo   ! CANH BAO CAO: PID %PORT_PID% KHONG phai Python
echo   ========================================
call :show_process_info %PORT_PID%
echo   Day CO THE la dich vu quan trong khac.
echo   Neu khong chac chan, HAY CHON [N] de bo qua.
echo.
call :prompt_user_kill N 20 %PORT_PID% Tier-3
if errorlevel 1 (
    echo [%date% %time%] User skipped kill (non-python safe default) PID %PORT_PID% >> "%LAUNCH_LOG%"
    set "KILL_FAILED=1"
    exit /b 0
)
goto :do_kill

:do_kill
taskkill /F /PID %PORT_PID% >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: taskkill failed for PID %PORT_PID% >> "%LAUNCH_LOG%"
    echo   CANH BAO: Khong tat duoc PID %PORT_PID%.
    set "KILL_FAILED=1"
) else (
    echo [%date% %time%] taskkill OK PID %PORT_PID% >> "%LAUNCH_LOG%"
    set "KILLED_PIDS=!KILLED_PIDS! %PORT_PID%"
)
exit /b 0

:show_process_info
set "INFO_PID=%~1"
set "PID_DIAG_FILE=%TMP_DIR%\vbsp_pid_diag_%INFO_PID%.txt"
del "%PID_DIAG_FILE%" >nul 2>&1
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=%INFO_PID%' -ErrorAction SilentlyContinue; if ($null -eq $p) { Write-Output '      Khong doc duoc thong tin tien trinh.' } else { $path=$p.ExecutablePath; if ([string]::IsNullOrWhiteSpace($path)) { $path='(khong doc duoc)' }; Write-Output ('      Ten: ' + $p.Name); Write-Output ('      Duong dan: ' + $path) }" > "%PID_DIAG_FILE%" 2>nul
if exist "%PID_DIAG_FILE%" (
    type "%PID_DIAG_FILE%"
    type "%PID_DIAG_FILE%" >> "%LAUNCH_LOG%"
)
del "%PID_DIAG_FILE%" >nul 2>&1
exit /b 0

:cleanup_stale_pid_marker
if not exist "%APP_PID_FILE%" exit /b 0
set "STALE_MARKER_PID="
for /f "usebackq tokens=1,* delims==" %%a in ("%APP_PID_FILE%") do (
    if /I "%%a"=="PID" set "STALE_MARKER_PID=%%b"
)
set "VBSP_STALE_MARKER_PID=!STALE_MARKER_PID!"
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$parsed=0; if (-not [int]::TryParse($env:VBSP_STALE_MARKER_PID, [ref]$parsed)) { exit 1 }; if ($null -eq (Get-Process -Id $parsed -ErrorAction SilentlyContinue)) { exit 1 }; exit 0" >nul 2>&1
set "VBSP_STALE_MARKER_PID="
if not errorlevel 1 exit /b 0
del "%APP_PID_FILE%" >nul 2>&1
if not exist "%APP_PID_FILE%" (
    echo [%date% %time%] Remove stale runtime PID marker >> "%LAUNCH_LOG%"
) else (
    echo [%date% %time%] WARN: cannot remove stale runtime PID marker >> "%LAUNCH_LOG%"
)
exit /b 0

:is_vbsp_process
rem Backward compatible: return 0 only for tier 0 (exact VBSP verification)
call :classify_pid_tier %~1
if "%errorlevel%"=="0" exit /b 0
exit /b 1

:classify_pid_tier
set "CLASSIFY_PID=%~1"
set "CLASSIFY_FILE=%TMP_DIR%\vbsp_classify_%CLASSIFY_PID%.txt"
set "CLASSIFY_PS1=%TMP_DIR%\vbsp_classify_%CLASSIFY_PID%.ps1"
del "%CLASSIFY_FILE%" >nul 2>&1
del "%CLASSIFY_PS1%" >nul 2>&1

call :is_marked_vbsp_process_classify %CLASSIFY_PID%
if not errorlevel 1 (
    del "%CLASSIFY_FILE%" >nul 2>&1
    del "%CLASSIFY_PS1%" >nul 2>&1
    exit /b 0
)

set "VBSP_CLASSIFY_PY_EXE=%PY_EXE%"
set "VBSP_CLASSIFY_ROOT=%ROOT%"

echo $p=Get-CimInstance Win32_Process -Filter 'ProcessId=%CLASSIFY_PID%' -ErrorAction SilentlyContinue ; > "%CLASSIFY_PS1%"
echo if ($null -eq $p) { Write-Output 'MISSING' ; exit 0 } >> "%CLASSIFY_PS1%"
echo $exe=[string]$p.ExecutablePath ; $cmd=[string]$p.CommandLine ; $name=[string]$p.Name ; >> "%CLASSIFY_PS1%"
echo $pyExe=$env:VBSP_CLASSIFY_PY_EXE ; $root=$env:VBSP_CLASSIFY_ROOT ; >> "%CLASSIFY_PS1%"
echo Write-Output ('EXE=' + $exe) ; >> "%CLASSIFY_PS1%"
echo Write-Output ('CMD=' + $cmd) ; >> "%CLASSIFY_PS1%"
echo Write-Output ('NAME=' + $name) ; >> "%CLASSIFY_PS1%"
echo $combined=($exe + ' ^| ' + $cmd).ToLowerInvariant() ; >> "%CLASSIFY_PS1%"
echo $pyExeNorm=$pyExe.ToLowerInvariant() ; $rootNorm=$root.ToLowerInvariant() ; >> "%CLASSIFY_PS1%"
echo $tier=3 ; >> "%CLASSIFY_PS1%"
echo $v0A = $combined.Contains($pyExeNorm) -or $combined.Contains($rootNorm + '\venv\') ; >> "%CLASSIFY_PS1%"
echo $v0B = $combined.Contains('streamlit') -or $combined.Contains('app.py') ; >> "%CLASSIFY_PS1%"
echo if ($v0A -and $v0B) { $tier=0 } >> "%CLASSIFY_PS1%"
echo elseif ($combined.Contains($rootNorm) -or $combined.Contains('\venv\') -or $combined.Contains('streamlit') -or $combined.Contains('app.py')) { $tier=1 } >> "%CLASSIFY_PS1%"
echo elseif ($name.ToLowerInvariant() -eq 'python.exe' -or $exe.ToLowerInvariant().EndsWith('python.exe') -or $exe.ToLowerInvariant().Contains('python3')) { $tier=2 } >> "%CLASSIFY_PS1%"
echo Write-Output ('TIER=' + $tier) ; >> "%CLASSIFY_PS1%"

powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%CLASSIFY_PS1%" > "%CLASSIFY_FILE%" 2>nul

del "%CLASSIFY_PS1%" >nul 2>&1

if not exist "%CLASSIFY_FILE%" goto :classify_fallback
for %%z in ("%CLASSIFY_FILE%") do if %%~zz EQU 0 goto :classify_fallback

set "CLASSIFY_TIER=3"
for /f "usebackq tokens=1,* delims==" %%a in ("%CLASSIFY_FILE%") do (
    if /I "%%a"=="TIER" set "CLASSIFY_TIER=%%b"
)
del "%CLASSIFY_FILE%" >nul 2>&1

if "%CLASSIFY_TIER%"=="0" exit /b 0
if "%CLASSIFY_TIER%"=="1" exit /b 1
if "%CLASSIFY_TIER%"=="2" exit /b 2
exit /b 3

:classify_fallback
del "%CLASSIFY_FILE%" >nul 2>&1
del "%CLASSIFY_PS1%" >nul 2>&1
set "FALLBACK_FILE=%TMP_DIR%\vbsp_fb_%CLASSIFY_PID%.txt"
where wmic.exe >nul 2>&1
if not errorlevel 1 wmic.exe process where "ProcessId=%CLASSIFY_PID%" get Name /format:list > "%FALLBACK_FILE%" 2>nul
set "FB_IS_PY=0"
findstr /I /L /C:"python.exe" "%FALLBACK_FILE%" >nul 2>&1
if not errorlevel 1 set "FB_IS_PY=1"
del "%FALLBACK_FILE%" >nul 2>&1
if "%FB_IS_PY%"=="1" exit /b 2
exit /b 3

:is_marked_vbsp_process_classify
if not exist "%APP_PID_FILE%" exit /b 1
set "MARKER_PID="
set "MARKER_ROOT="
set "MARKER_APP="
for /f "usebackq tokens=1,* delims==" %%a in ("%APP_PID_FILE%") do (
    if /I "%%a"=="PID" set "MARKER_PID=%%b"
    if /I "%%a"=="ROOT" set "MARKER_ROOT=%%b"
    if /I "%%a"=="APP" set "MARKER_APP=%%b"
)
if not "!MARKER_PID!"=="%~1" exit /b 1
if /I not "!MARKER_ROOT!"=="%ROOT%" exit /b 1
if /I not "!MARKER_APP!"=="%ROOT%\app.py" exit /b 1
exit /b 0

:prompt_user_kill
set "PK_DEFAULT=%~1"
set "PK_TIMEOUT=%~2"
set "PK_PID=%~3"
set "PK_TIER=%~4"
set "PK_PROMPT_FILE=%TMP_DIR%\vbsp_prompt_%PK_PID%.txt"
del "%PK_PROMPT_FILE%" >nul 2>&1

rem Use choice.exe if available; fallback to set /p
where choice.exe >nul 2>&1
if errorlevel 1 goto :prompt_user_kill_fallback

echo   Tiep tuc: Dong tien trinh PID %PK_PID%?
choice /C YN /T %PK_TIMEOUT% /D %PK_DEFAULT% /M "   Lua chon [Y=Dong, N=Bo qua] (mac dinh %PK_DEFAULT% sau %PK_TIMEOUT%s)"
set "PK_RC=%errorlevel%"
del "%PK_PROMPT_FILE%" >nul 2>&1
if "%PK_RC%"=="1" exit /b 0
exit /b 1

:prompt_user_kill_fallback
set /P "PK_ANSWER=   Dong tien trinh PID %PK_PID%? [Y/N, mac dinh %PK_DEFAULT% sau %PK_TIMEOUT%s]: "
if "%PK_ANSWER%"=="" set "PK_ANSWER=%PK_DEFAULT%"
del "%PK_PROMPT_FILE%" >nul 2>&1
if /I "%PK_ANSWER%"=="Y" exit /b 0
exit /b 1

:prompt_alt_port_or_exit
echo.
echo   ----------------------------------------------
echo   Lua chon giai phap cong %PORT% van bi chiem:
echo     [1] Su dung cong thay the %ALT_PORT% (de xuat)
echo     [2] Thu dong cac tien trinh con lai tren cong %PORT%
echo     [3] Thoat (dung co che)
echo   ----------------------------------------------
where choice.exe >nul 2>&1
if errorlevel 1 goto :prompt_alt_port_fallback

choice /C 123 /T 15 /D 1 /M "   Chon [1/2/3] (mac dinh 1 sau 15s)"
set "PAP_RC=%errorlevel%"
goto :dispatch_alt_port_choice

:prompt_alt_port_fallback
set /P "PAP_ANSWER=   Nhap 1, 2 hoac 3 (mac dinh 1): "
if "%PAP_ANSWER%"=="" set "PAP_ANSWER=1"
if "%PAP_ANSWER%"=="1" set "PAP_RC=1"
if "%PAP_ANSWER%"=="2" set "PAP_RC=2"
if "%PAP_ANSWER%"=="3" set "PAP_RC=3"
goto :dispatch_alt_port_choice

:dispatch_alt_port_choice
if "%PAP_RC%"=="3" (
    echo [%date% %time%] User chose abort on port conflict >> "%LAUNCH_LOG%"
    exit /b 1
)
if "%PAP_RC%"=="2" (
    echo [%date% %time%] Retry kill with --force-kill semantics for this round >> "%LAUNCH_LOG%"
    set "FORCE_KILL=true"
    call :kill_port_processes
    if errorlevel 1 (
        rem Still failing after force-kill attempt: force option 1
        set "PAP_RC=1"
        goto :switch_to_alt_port
    )
    set "FORCE_KILL=false"
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        rem Port freed
        exit /b 0
    )
    rem Port still occupied, offer alt port again
    echo   Port %PORT% van con bi chiem sau khi thu tat cuong che.
    goto :switch_to_alt_port
)
:switch_to_alt_port
set "PORT=%ALT_PORT%"
set "URL=http://localhost:%ALT_PORT%"
echo [%date% %time%] Switched to alternate port %PORT% >> "%LAUNCH_LOG%"
echo.
echo   => Da chuyen sang su dung cong: %PORT%
echo   => URL: %URL%
echo.
exit /b 0

:calculate_requirements_hash
set "REQ_HASH="
set "REQ_HASH_FILE=%TMP_DIR%\requirements_hash.txt"
if not exist "%REQUIREMENTS_FILE%" (
    echo [%date% %time%] ERROR: requirements.txt not found >> "%LAUNCH_LOG%"
    echo   LOI: Khong tim thay %REQUIREMENTS_FILE%
    exit /b 1
)
if not exist "%REQUIREMENTS_LOCK_FILE%" (
    echo [%date% %time%] ERROR: requirements.lock.txt not found >> "%LAUNCH_LOG%"
    echo   LOI: Khong tim thay %REQUIREMENTS_LOCK_FILE%
    exit /b 1
)
"%PY_EXE%" "%ROOT%\scripts\validate_dependency_lock.py" "%REQUIREMENTS_FILE%" "%REQUIREMENTS_LOCK_FILE%" >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: dependency lock is inconsistent >> "%LAUNCH_LOG%"
    echo   LOI: requirements.txt va requirements.lock.txt khong dong bo.
    exit /b 1
)
del "%REQ_HASH_FILE%" >nul 2>&1
set "VBSP_REQUIREMENTS_FILE=%REQUIREMENTS_FILE%"
set "VBSP_REQUIREMENTS_LOCK_FILE=%REQUIREMENTS_LOCK_FILE%"
set "VBSP_REQUIREMENTS_HASH_FILE=%REQ_HASH_FILE%"
"%PY_EXE%" -c "import hashlib, os; from pathlib import Path; src=Path(os.environ['VBSP_REQUIREMENTS_FILE']); lock=Path(os.environ['VBSP_REQUIREMENTS_LOCK_FILE']); dst=Path(os.environ['VBSP_REQUIREMENTS_HASH_FILE']); dst.write_text(hashlib.sha256(src.read_bytes()+b'\0'+lock.read_bytes()).hexdigest(), encoding='ascii')" >nul 2>&1
if exist "%REQ_HASH_FILE%" set /p "REQ_HASH="<"%REQ_HASH_FILE%"
del "%REQ_HASH_FILE%" >nul 2>&1
if not defined REQ_HASH (
    echo [%date% %time%] ERROR: cannot hash dependency files >> "%LAUNCH_LOG%"
    echo   LOI: Khong the kiem tra thay doi dependency.
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
    echo [%date% %time%] dependency lock unchanged >> "%LAUNCH_LOG%"
    exit /b 0
)

echo.
echo -- Dependency lock da thay doi, dang dong bo thu vien... --
echo   Chi chay khi requirements/lockfile thay doi.
echo [%date% %time%] dependency hash changed: %SAVED_REQ_HASH% to %REQ_HASH% >> "%LAUNCH_LOG%"
"%PY_EXE%" -m pip install "pip==%PIP_VERSION%" --quiet >> "%LAUNCH_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: pinned pip install failed >> "%LAUNCH_LOG%"
    echo   LOI: Khong cai duoc pip %PIP_VERSION%. Xem log: %LAUNCH_LOG%
    exit /b 1
)
"%PY_EXE%" -m pip install --no-deps -r "%REQUIREMENTS_LOCK_FILE%" >> "%LAUNCH_LOG%" 2>&1
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
set "SEEN_PIDS="
call :register_pid_once 4456
if errorlevel 1 (
    echo LAUNCHER SELF-TEST FAILED: PID dedup first value
    exit /b 1
)
call :register_pid_once 4456
if not errorlevel 1 (
    echo LAUNCHER SELF-TEST FAILED: PID dedup duplicate
    exit /b 1
)
call :register_pid_once 7788
if errorlevel 1 (
    echo LAUNCHER SELF-TEST FAILED: PID dedup second value
    exit /b 1
)
echo LAUNCHER SELF-TEST OK
exit /b 0

:cleanup
rmdir "%LOCK_DIR%" >nul 2>&1
exit /b 0
