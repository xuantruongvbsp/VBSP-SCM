@echo off
:: ============================================================
:: setup_health_check_task.bat
:: Cài Windows Task Scheduler chạy health_check.py lúc 6:30
:: Chạy với quyền Administrator: chuột phải → Run as administrator
:: ============================================================
setlocal

set TASK_NAME=VBSP_SCM_HealthCheck
set PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe
set SCRIPT=D:\VBSP-SCM\health_check.py
set LOG_DIR=D:\VBSP-SCM\logs
set LOG_FILE=%LOG_DIR%\health_check.log

:: Tạo thư mục log nếu chưa có
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Xóa task cũ nếu tồn tại (tránh duplicate)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Tạo task mới — chạy mỗi ngày lúc 06:30
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\" >> \"%LOG_FILE%\" 2>&1" ^
  /sc daily ^
  /st 06:30 ^
  /ru "%USERNAME%" ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Task da duoc cai dat thanh cong!
    echo      Ten task : %TASK_NAME%
    echo      Chay luc : 06:30 hang ngay
    echo      Log      : %LOG_FILE%
    echo.
    echo Kiem tra: Task Scheduler ^> Task Scheduler Library ^> %TASK_NAME%
) else (
    echo.
    echo [LOI] Khong tao duoc task. Hay chay script nay voi quyen Administrator.
)

pause
endlocal
