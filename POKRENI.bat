@echo off
title KestrelScan
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python nije pronadjen.
  echo   Instaliraj ga sa python.org i obavezno cekiraj "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

if not exist ".venv\" (
  echo   Prvo pokretanje - pripremam okruzenje, potrajace minut...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

python app.py
pause
