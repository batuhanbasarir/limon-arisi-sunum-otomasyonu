@echo off
cd /d "%~dp0"
title Limon Arisi Sunum Otomasyonu

if not exist ".venv\Scripts\python.exe" (
    echo [HATA] .venv bulunamadi. Once "python -m venv .venv" ve "pip install -r backend\requirements.txt" calistirin.
    pause
    exit /b 1
)

echo Limon Arisi sunucusu baslatiliyor...
start "Limon Arisi Sunucu" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000"

echo Tarayici aciliyor (birkac saniye surebilir)...
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000"

exit /b 0
