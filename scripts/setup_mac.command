#!/bin/bash
cd "$(dirname "$0")/.."

echo "======================================================="
echo "   LectureFlow - Configuración Inicial (macOS)"
echo "======================================================="

# 1. Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 no está instalado o no se encuentra en el PATH."
    exit 1
fi

# 2. Verificar e instalar FFmpeg vía Homebrew si falta
if ! command -v ffmpeg &> /dev/null; then
    echo "[ADVERTENCIA] FFmpeg no detectado."
    if command -v brew &> /dev/null; then
        echo "[INFO] Instalando FFmpeg vía Homebrew..."
        brew install ffmpeg
    else
        echo "[ERROR] Homebrew no instalado. Por favor instala FFmpeg manualmente (brew install ffmpeg)."
    fi
else
    echo "[ÉXITO] FFmpeg detectado correctamente."
fi

# 3. Crear entorno virtual 'venv' si no existe
if [ ! -d "venv" ]; then
    echo "[INFO] Creando entorno virtual 'venv'..."
    python3 -m venv venv
fi

# 4. Activar entorno e instalar dependencias
echo "[INFO] Activando entorno virtual e instalando dependencias..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-mac.txt

echo ""
echo "======================================================="
echo "Configuración completada. Ya puedes lanzar LectureFlow con:"
echo "Iniciar_Mac.command"
echo "======================================================="
