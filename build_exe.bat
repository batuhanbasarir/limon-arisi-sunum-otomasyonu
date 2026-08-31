@echo off
cd /d "%~dp0"
echo Limon Arisi masaustu .exe'si derleniyor...

if not exist ".venv\Scripts\python.exe" (
    echo [HATA] .venv bulunamadi. Once "python -m venv .venv" ve "pip install -r backend\requirements.txt" calistirin.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller kuruluyor...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
)

".venv\Scripts\python.exe" -m PyInstaller --onefile --noconfirm --clean ^
  --name "LimonArisiSunum" ^
  --icon "app_icon.ico" ^
  --add-data "templates;templates" ^
  --add-data "frontend;frontend" ^
  --paths backend ^
  --collect-all imageio_ffmpeg ^
  backend\app\desktop_launcher.py

echo.
echo Bitti. .exe dosyasi: dist\LimonArisiSunum.exe
pause
