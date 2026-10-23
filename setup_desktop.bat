@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ================================================
echo Market Intelligence Lab - Windows Desktop Setup
echo ================================================
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python was not found. Install Python 3.11-3.13 from python.org and enable Add Python to PATH.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
) else (
  set "PYTHON_CMD=py -3"
)
%PYTHON_CMD% -c "import sys; print('Detected Python:', sys.version); raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)"
if errorlevel 1 (
  echo [ERROR] Use Python 3.11, 3.12, or 3.13. Existing system Python will not be replaced.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating local virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :error
)
echo [INFO] Updating pip inside the local environment...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
echo [INFO] Installing desktop and analysis dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt
if errorlevel 1 goto :error
echo [INFO] Running automated tests...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
  echo [WARNING] One or more tests failed. Review the output before relying on the app.
  pause
  exit /b 1
)
echo.
echo [SUCCESS] Setup complete. Double-click run_desktop.bat to launch the desktop app.
pause
exit /b 0
:error
echo.
echo [ERROR] Setup failed. Check your internet connection and the error above.
echo Your global Python installation was not replaced.
pause
exit /b 1
