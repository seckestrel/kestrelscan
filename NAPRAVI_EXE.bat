@echo off
setlocal enabledelayedexpansion
title KestrelScan - pravljenje .exe
cd /d "%~dp0"

rem --- nadji Python isto kao POKRENI.bat ---
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY call :proba "py -3"
if not defined PY call :proba "python"
if not defined PY call :proba "python3"
if not defined PY (
  echo.
  echo   Python nije pronadjen. Instaliraj ga sa python.org
  echo   i cekiraj "Add python.exe to PATH", pa pokreni ovo ponovo.
  echo.
  pause
  exit /b 1
)

echo   Pravim samostalni KestrelScan.exe sa: !PY!
echo.

!PY! -m pip install --quiet --upgrade pyinstaller
!PY! -m pip install --quiet -r requirements.txt

!PY! -m PyInstaller --noconfirm --onefile --name KestrelScan ^
  --add-data "sabloni;sabloni" ^
  --add-data "statika;statika" ^
  --add-data "fontovi;fontovi" ^
  --hidden-import dns.resolver ^
  --hidden-import dns.rdatatype ^
  --collect-all reportlab ^
  app.py

echo.
echo   Gotovo. Exe je u folderu dist\
echo.
echo   Na USB kopiraj:
echo      dist\KestrelScan.exe
echo      postavke.json        (kljucevi i potpis)
echo      tools\               (PingCastle.exe, ako ga koristis)
echo.
echo   Folder rezultati\ se pravi sam, pored exe-a.
echo.
pause
exit /b

:proba
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b
