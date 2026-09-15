# Asistente DAW

Un asistente unificado y multiplataforma con ejecución "cero terminal".

## Requisitos previos
- Tener Python instalado (recomendado Python 3.9+).
- Tener Ollama instalado y corriendo (en Windows el script intentará levantarlo si no lo está).
- FFmpeg instalado y disponible en el PATH del sistema.

## Configuración Inicial

### En macOS
1. Abre la terminal en esta carpeta y ejecuta `bash scripts/setup_mac.sh`. (Solo la primera vez).
2. Crea un archivo `.env` basado en `.env.example` y pon tus credenciales de Notion.

### En Windows
1. Haz doble clic en `scripts\setup_windows.bat`. (Solo la primera vez).
2. Crea un archivo `.env` basado en `.env.example` y pon tus credenciales de Notion.

## Iniciar la aplicación

- **En macOS:** Simplemente haz doble clic en el archivo `Iniciar_Mac.command`.
- **En Windows:** Haz doble clic en el archivo `Iniciar_Windows.vbs` (esto la iniciará en segundo plano ocultando la terminal).

*(Nota: Asegúrate de tener los modelos de Ollama descargados, como `llama3` o el que uses en tu configuración).*
