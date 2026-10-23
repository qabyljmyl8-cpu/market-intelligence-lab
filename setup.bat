@echo off
setlocal
cd /d "%~dp0"
title Market Intelligence Lab - Setup
echo ======================================================
echo   Market Intelligence Lab - Windows Setup
echo ======================================================
set "PYTHON_CMD="
where py >nul 2>nul
if errorlevel 1 goto CHECK_PYTHON
py -3.13 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.13"
if defined PYTHON_CMD goto PYTHON_FOUND
py -3.14 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.14"
if defined PYTHON_CMD goto PYTHON_FOUND
py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if defined PYTHON_CMD goto PYTHON_FOUND
py -3.11 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.11"
if defined PYTHON_CMD goto PYTHON_FOUND
:CHECK_PYTHON
where python >nul 2>nul
if errorlevel 1 goto PYTHON_MISSING
set "PYTHON_CMD=python"
:PYTHON_FOUND
echo Checking installed Python...
%PYTHON_CMD% --version
if errorlevel 1 (echo ERROR: Could not run Python.& pause & exit /b 1)
%PYTHON_CMD% -c "import sys; ok=(3,11) <= sys.version_info[:2] <= (3,14); print('Supported Python version.' if ok else 'Unsupported Python version: install Python 3.11 through 3.14.'); raise SystemExit(0 if ok else 2)"
if errorlevel 1 (echo ERROR: Python 3.11-3.14 is required. No global Python version was changed.& pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo Creating project-local virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (echo ERROR: Could not create .venv.& pause & exit /b 1)
) else (
  echo Existing .venv found; keeping it.
)
echo Updating pip inside this project's virtual environment...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (echo ERROR: pip upgrade failed. Check internet access.& pause & exit /b 1)
echo Installing project dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo ERROR: dependency installation failed. Check internet access and requirements.txt.& pause & exit /b 1)
echo Verifying core imports...
".venv\Scripts\python.exe" -c "import streamlit,pandas,numpy,plotly,ccxt,pydantic,requests; print('Core imports OK')"
if errorlevel 1 (echo ERROR: a core dependency cannot be imported.& pause & exit /b 1)
echo.
echo Setup complete. Start the app with run_app.bat
pause
exit /b 0
:PYTHON_MISSING
echo ERROR: Python was not found. Install Python 3.11-3.14 from python.org and enable the launcher or PATH.
pause
exit /b 1
