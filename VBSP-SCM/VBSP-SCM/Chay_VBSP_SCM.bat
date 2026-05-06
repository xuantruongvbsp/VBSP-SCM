@echo off
cd /d %~dp0
echo Dang khoi dong VBSP-SCM...
echo.
python -m streamlit run app.py
pause
