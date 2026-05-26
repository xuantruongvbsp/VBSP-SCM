@echo off
REM setup_daily_report_task.bat — Cài đặt Windows Task Scheduler chạy daily_report.py lúc 07:00 hằng ngày.
REM Chạy với quyền Administrator.
REM Tự động detect Python từ môi trường hiện tại.

cd /d "%~dp0.."

for /f "tokens=*" %%i in ('where python') do set PYTHON=%%i
if "%PYTHON%"=="" set PYTHON=python

set SCRIPT_DIR=%CD%
set REPORT_SCRIPT=%SCRIPT_DIR%\scripts\daily_report.py
set LOG_DIR=%SCRIPT_DIR%\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

schtasks /Create /F /SC DAILY /TN "VBSP-SCM_DailyReport" /TR "\"%PYTHON%\" \"%REPORT_SCRIPT%\" >> \"%LOG_DIR%\daily_report.log\" 2>&1" /ST 07:00 /RU SYSTEM

if %ERRORLEVEL% EQU 0 (
    echo ✅ Đã cài đặt Task Scheduler "VBSP-SCM_DailyReport" — chạy lúc 07:00 mỗi ngày.
    echo    Script: %REPORT_SCRIPT%
    echo    Log:    %LOG_DIR%\daily_report.log
) else (
    echo ❌ Lỗi cài đặt Task Scheduler. Kiểm tra quyền Administrator.
)

pause
