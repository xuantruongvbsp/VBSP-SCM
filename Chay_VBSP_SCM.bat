@echo off
cd /d %~dp0
echo Dang khoi dong VBSP-SCM...
start /b .\.venv\Scripts\streamlit run app.py
timeout /t 4 /nobreak >nul
start "" http://localhost:8501
echo Server dang chay tai http://localhost:8501
pause
