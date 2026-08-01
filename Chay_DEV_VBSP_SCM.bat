@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"
echo.
echo ============================================
echo   VBSP-SCM - DEV launcher
echo ============================================
echo.
echo Che do nay khong mo them tab Chrome.
echo Hay giu 1 tab duy nhat:
echo   http://localhost:8502
echo.
echo Khi sua code, Streamlit se tu reload neu file watcher bat duoc thay doi.
echo Neu can restart server, chay lai file nay; tab Chrome cu se tu ket noi lai.
echo.

call "%~dp0Chay_VBSP_SCM.bat" --no-browser
