@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Duong dan phu de tuong thich nguoc.
rem Launcher chinh va duy nhat: Chay_VBSP_SCM.bat
call "%~dp0Chay_VBSP_SCM.bat" %*
set "APP_RC=%errorlevel%"
exit /b %APP_RC%
