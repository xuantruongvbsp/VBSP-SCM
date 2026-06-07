@echo off
REM Đăng ký Task Scheduler chạy backup lúc 06:30 mỗi ngày
REM Chạy file này với quyền Administrator

SET TASK_NAME=VBSP-SCM_Backup
SET PYTHON_PATH=%~dp0..\venv\Scripts\python.exe
SET SCRIPT_PATH=%~dp0backup_daily.py
SET LOG_PATH=%~dp0..\logs\backup_scheduler.log

echo [%DATE% %TIME%] Dang dang ky scheduled task... >> "%LOG_PATH%"

schtasks /Delete /TN "%TASK_NAME%" /F >/dev/null 2>&1

schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
  /SC DAILY ^
  /ST 06:30 ^
  /RU SYSTEM ^
  /RL HIGHEST ^
  /F

IF %ERRORLEVEL% EQU 0 (
    echo ✅ Da dang ky task: %TASK_NAME% chay luc 06:30 hang ngay
    echo [%DATE% %TIME%] Thanh cong >> "%LOG_PATH%"
) ELSE (
    echo ❌ Dang ky that bai. Chay lai voi quyen Administrator.
    echo [%DATE% %TIME%] That bai >> "%LOG_PATH%"
    exit /b 1
)

echo Kiem tra: schtasks /Query /TN "%TASK_NAME%"
schtasks /Query /TN "%TASK_NAME%"
