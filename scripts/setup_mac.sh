#!/bin/bash
echo "==================================="
echo "Instalando dependencias de macOS"
echo "==================================="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-mac.txt
echo "Finalizado. Ya puedes usar Iniciar_Mac.command"
