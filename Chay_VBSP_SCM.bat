@echo off
cd /d %~dp0
echo Dang khoi dong VBSP-SCM...
start "" http://localhost:8501
.\.venv\Scripts\streamlit run app.py
pause
