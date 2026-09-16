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

:: Lanzar el navegador manualmente en paralelo para asegurar que abra la pestaña
start "" http://localhost:8501

:: Iniciar Streamlit en el puerto base
python -m streamlit run app.py --server.port 8501 --server.headless true