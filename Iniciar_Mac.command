#!/bin/bash
cd "$(dirname "$0")"

# Abrir el navegador en el puerto 8000
(sleep 2 && open "http://127.0.0.1:8000") &

# Arrancar el servidor unificado FastAPI (Frontend React + API REST)
venv/bin/python -m uvicorn src.api.main:app --port 8000 --host 127.0.0.1

