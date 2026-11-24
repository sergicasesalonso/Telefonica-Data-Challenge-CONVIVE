@echo off
rem CONVIVE dashboard (WBS 4.3.2). Runs only on this computer: http://localhost:8501
cd /d "%~dp0"
python -m streamlit run app/dashboard.py
if errorlevel 1 (
  echo.
  echo The dashboard did not start. Install the requirements first:
  echo     python -m pip install -r requirements.txt
  pause
)
