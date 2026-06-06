@echo off
chcp 65001 >nul
cd /d D:\VBSP-SCM

:: Tạo thư mục logs nếu chưa có
if not exist logs mkdir logs

:: Tên file log theo timestamp (dùng PowerShell — tránh bug WMIC CR)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set _ts=%%I
set LOGFILE=logs\health_%_ts%.txt

echo.
echo ========================================
echo  VBSP-SCM -- Full Health Check + Tests
echo  Log: %LOGFILE%
echo ========================================
echo.

:: Header log
(
echo VBSP-SCM Health Check + Test Run
echo Thoi gian: %date% %time%
echo ========================================
) > "%LOGFILE%"

echo.
echo [0/3] Kiem tra dependencies...
echo.
pip install pyarrow pytest-cov -q
echo.

echo [1/3] Health Check he thong...
echo.
python health_check.py
python health_check.py >> "%LOGFILE%" 2>&1

echo.
echo [2/3] Chay test suite...
echo.
pytest tests/ -v --tb=short
pytest tests/ -v --tb=short >> "%LOGFILE%" 2>&1

echo.
echo [3/3] Coverage report...
echo.
pytest tests/ --cov=. --cov-report=term-missing -q
pytest tests/ --cov=. --cov-report=term-missing -q >> "%LOGFILE%" 2>&1

echo.
echo ========================================
echo  Hoan thanh! Log da luu: %LOGFILE%
echo ========================================
echo.
pause
