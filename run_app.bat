@echo off
setlocal
cd /d "%~dp0"
title Market Intelligence Lab
if not exist ".venv\Scripts\python.exe" (
  echo The project environment was not found. Run setup.bat first.
  pause
  exit /b 1
)
echo Starting Market Intelligence Lab...
echo Streamlit will print a local URL, usually http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 (
  echo.
  echo The application exited with an error. Review the output above.
  pause
)
