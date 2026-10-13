@echo off
setlocal
cd /d "%~dp0"
if exist "windows\MagicUndicer.exe" (
  start "" "windows\MagicUndicer.exe" %*
  exit /b 0
)
if exist "MagicUndicer.exe" (
  start "" "MagicUndicer.exe" %*
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -c "import magicundicer.gui, tkinterdnd2" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install ".[gui]"
  if errorlevel 1 goto :failed
)
start "" ".venv\Scripts\pythonw.exe" -m magicundicer.gui %*
exit /b 0
:failed
echo Setup failed. Install Python 3.10 or newer and try again.
pause
exit /b 1
