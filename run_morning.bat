@echo off
cd /d D:\VBSP-SCM

set LOGFILE=cache\morning_log.txt
if not exist cache mkdir cache

echo. >> %LOGFILE%
echo === %date% %time% === >> %LOGFILE%

venv\Scripts\python.exe scripts\daily_report.py >> %LOGFILE% 2>&1
venv\Scripts\python.exe scripts\nhac_deadline.py >> %LOGFILE% 2>&1

echo --- Xong --- >> %LOGFILE%
