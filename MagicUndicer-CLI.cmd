@echo off
setlocal
cd /d "%~dp0"
if exist "windows\MagicUndicer-CLI.exe" goto :bundled
if exist "MagicUndicer-CLI.exe" goto :exe
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating a Python environment...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -c "import magicundicer" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install .
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m magicundicer %*
set "undice_status=%errorlevel%"
pause
exit /b %undice_status%
:bundled
"windows\MagicUndicer-CLI.exe" %*
set "undice_status=%errorlevel%"
pause
exit /b %undice_status%
:exe
"MagicUndicer-CLI.exe" %*
set "undice_status=%errorlevel%"
pause
exit /b %undice_status%
:failed
echo Setup failed. Install Python 3.10 or newer and try again.
pause
exit /b 1
