@echo off
title KestrelScan - pravljenje .exe
cd /d "%~dp0"

echo   Pravim samostalni KestrelScan.exe ...
echo.

python -m pip install --quiet --upgrade pyinstaller
python -m pip install --quiet -r requirements.txt

python -m PyInstaller --noconfirm --onefile --name KestrelScan ^
  --add-data "sabloni;sabloni" ^
  --add-data "statika;statika" ^
  --add-data "fontovi;fontovi" ^
  --hidden-import dns.resolver ^
  --hidden-import dns.rdatatype ^
  --collect-all reportlab ^
  app.py

echo.
echo   Gotovo. Exe je u folderu dist\
echo   Kopiraj na USB: KestrelScan.exe + folder tools\
echo.
pause
