@echo off
setlocal enabledelayedexpansion
title KestrelScan
cd /d "%~dp0"

rem --- Ako je okruzenje vec napravljeno, koristi njegov python direktno ---
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
  pause
  exit /b
)

rem --- Trazi Python: prvo pokretac py, pa python, pa uobicajene putanje ---
set "PY="
call :proba "py -3"
if not defined PY call :proba "python"
if not defined PY call :proba "python3"
if not defined PY call :trazi_po_disku

if not defined PY (
  echo.
  echo   Python nije pronadjen na ovom racunaru.
  echo.
  echo   Dvije mogucnosti:
  echo.
  echo   1^) Instaliraj Python sa https://www.python.org/downloads/
  echo      i OBAVEZNO cekiraj "Add python.exe to PATH" na prvom ekranu.
  echo.
  echo   2^) Ili na svom racunaru pokreni NAPRAVI_EXE.bat jednom,
  echo      pa KestrelScan.exe radi na svakoj masini bez Pythona.
  echo.
  pause
  exit /b 1
)

echo   Koristim: !PY!
echo   Prvo pokretanje - pripremam okruzenje, potrajace minut...
!PY! -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Pravljenje okruzenja nije uspjelo. Pokrecem bez njega.
  echo.
  !PY! -m pip install --quiet -r requirements.txt
  !PY! app.py
  pause
  exit /b
)
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
".venv\Scripts\python.exe" app.py
pause
exit /b

rem ---------------------------------------------------------------
rem Provjeri da li zadata komanda stvarno pokrece Python 3.9 ili noviji.
rem Ovo odbacuje i praznu ljusku iz Microsoft Store-a, koja postoji u
rem PATH-u ali ne pokrece nista.
rem ---------------------------------------------------------------
:proba
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b

rem --- Instaliran je, ali nije u PATH-u: potrazi ga na uobicajenim mjestima ---
:trazi_po_disku
for %%D in (
  "%LocalAppData%\Programs\Python"
  "%ProgramFiles%\Python313" "%ProgramFiles%\Python312"
  "%ProgramFiles%\Python311" "%ProgramFiles%\Python310"
  "C:\Python313" "C:\Python312" "C:\Python311" "C:\Python310"
) do (
  if exist "%%~D" (
    for /f "delims=" %%P in ('dir /b /s "%%~D\python.exe" 2^>nul') do (
      if not defined PY call :proba "%%P"
    )
  )
)
exit /b
