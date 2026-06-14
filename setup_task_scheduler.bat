@echo off
echo ============================================
echo  Cai dat tu dong VBSP-SCM Morning Task
echo ============================================
echo.

:: Kiem tra quyen Admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Can chay voi quyen Administrator!
    echo.
    echo Huong dan: Chuot phai vao file nay ^> "Run as administrator"
    echo.
    pause
    exit /b 1
)

:: Tao task chay luc 6:30 sang moi ngay
schtasks /create /tn "VBSP-SCM Bao cao sang" ^
    /tr "D:\VBSP-SCM\run_morning.bat" ^
    /sc daily ^
    /st 06:30 ^
    /f >nul 2>&1

if %errorlevel% == 0 (
    echo [OK] Da tao task thanh cong!
    echo.
    echo Lich chay: 6:30 sang moi ngay
    echo Script    : D:\VBSP-SCM\run_morning.bat
    echo Log       : D:\VBSP-SCM\cache\morning_log.txt
    echo.
    echo Ban se nhan Telegram moi sang luc 6:30.
) else (
    echo [LOI] Khong tao duoc task.
    echo Thu lai hoac lien he ky thuat.
)

echo.
pause
