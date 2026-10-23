@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found. Run setup_desktop.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" desktop_app.py
if errorlevel 1 (
  echo.
  echo The desktop application closed with an error. Check market_intelligence_lab.log.
  pause
)
endlocal
