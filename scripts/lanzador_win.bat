@echo off
cd /d "%~dp0\.."

tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo Iniciando Ollama en background...
    start "" /B ollama serve
)

call venv_win\Scripts\activate.bat
streamlit run app.py
