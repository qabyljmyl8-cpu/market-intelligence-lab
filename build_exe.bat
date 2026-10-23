@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_desktop.bat first.
  pause
  exit /b 1
)
echo Building a Windows executable. This can take several minutes...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name MarketIntelligenceLab --collect-all PySide6 --collect-all ccxt --hidden-import=pandas --hidden-import=numpy desktop_app.py
if errorlevel 1 (
  echo Build failed. Review the output above.
  pause
  exit /b 1
)
echo Build complete: dist\MarketIntelligenceLab\MarketIntelligenceLab.exe
echo Keep the entire dist\MarketIntelligenceLab folder together because it contains runtime files and local dependencies.
pause
endlocal
