@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=0
cd /d "%~dp0\.."

echo =======================================================
echo    LectureFlow - Configuracion Inicial (Windows)
echo =======================================================

:: 1. Verificar Python en PATH
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python no esta en el PATH del sistema.
    echo Por favor instala Python 3.10+ marcando "Add Python to PATH".
    pause
    exit /b 1
)

:: 2. Crear entorno virtual si no existe
if not exist "venv_win" (
    echo [INFO] Creando entorno virtual 'venv_win'...
    python -m venv venv_win
)

:: 3. Activar entorno e instalar dependencias
echo [INFO] Activando entorno virtual e instalando dependencias...
call venv_win\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-win.txt

:: 4. Verificar e intentar instalar FFmpeg si falta
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ADVERTENCIA] FFmpeg no fue detectado en el PATH.
    echo Intentando instalacion silenciosa con winget...
    winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] No se pudo instalar FFmpeg automaticamente.
        echo Por favor instala FFmpeg manualmente y agregalo al PATH.
    ) else (
        echo [EXITO] FFmpeg instalado correctamente.
    )
) else (
    echo [EXITO] FFmpeg detectado correctamente.
)

echo.
echo =======================================================
echo Configuracion completada. Ya puedes lanzar LectureFlow con:
echo Iniciar_Windows.vbs
echo =======================================================
pause
