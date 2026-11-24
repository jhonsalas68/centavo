@echo off
title OmniDownloader Server
echo ========================================================
echo       Iniciando OmniDownloader (Video Downloader)
echo ========================================================
echo.
echo Comprobando entorno virtual...
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Entorno virtual no encontrado. Ejecuta 'python -m venv venv' e instala las dependencias.
    pause
    exit /b
)

echo Abriendo navegador en http://localhost:8000...
start http://localhost:8000

echo Iniciando servidor FastAPI con Uvicorn...
.\venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

pause
