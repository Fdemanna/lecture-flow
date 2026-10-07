@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=0
cd /d "%~dp0\.."

tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    start "" /B ollama serve
    timeout /t 2 /nobreak >nul
)

call ".\venv_win\Scripts\activate.bat"

:: Lanzar el navegador apuntando a la SPA unificada en FastAPI
start "" http://127.0.0.1:8000

:: Iniciar FastAPI con Uvicorn en el puerto 8000
python -m uvicorn src.api.main:app --port 8000 --host 127.0.0.1