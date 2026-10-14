@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Nedostaje lokalni .venv. Prati instalaciju u README.md. 1>&2
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" -m atlas %*
exit /b %errorlevel%
