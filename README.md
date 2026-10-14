# LectureFlow

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen_2.5_7B-000000?logo=ollama&logoColor=white)](https://ollama.com)
[![Platform](https://img.shields.io/badge/Platform-macOS_(Metal)_%7C_Windows_(CUDA)-lightgrey)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Convierte grabaciones, diapositivas y PDFs de clase en apuntes Markdown y sesiones de repaso espaciado, todo en tu máquina y sin APIs de pago.**

---

## Por qué lo construimos

Trabajo 9 horas al día en hostelería y estudio desarrollo de software por la tarde. Cuando llegas a clase después de un turno, puedes hacer una de dos cosas: tomar apuntes o entender lo que te están explicando. Las dos a la vez no salen.

LectureFlow lo construimos entre un compañero y yo para quitar de en medio la parte mecánica: transcribir, ordenar, pasar a limpio, preparar preguntas de repaso. La clase se graba (o se descargan las diapositivas), el pipeline hace el trabajo pesado en local mientras duermes o trabajas, y al día siguiente tienes apuntes estructurados y un test listo para repasar.

Las restricciones eran claras: portátiles normales con 8–16 GB de memoria, cero presupuesto para APIs y nada de subir grabaciones de clase a servidores de terceros.

---

## Arquitectura y pipeline

```text
  ENTRADA                                PROCESAMIENTO (local)                         SALIDA
 ─────────                              ───────────────────────                       ────────

 ┌──────────────────┐
 │ URL remota       │──► yt-dlp ──┐     (solo pista de audio, .m4a)
 │ (Blackboard, YT) │             │
 └──────────────────┘             ▼
 ┌──────────────────┐     ┌──────────────────────┐
 │ Audio / Vídeo    │────►│ Subproceso Whisper   │  large-v3-turbo
 │ (mp4 mkv mp3 …)  │     │ mlx (Metal) / CUDA   │  muere al terminar → VRAM a 0
 └──────────────────┘     └──────────┬───────────┘
                                     │ transcripcion.txt  [HH:MM:SS]
 ┌──────────────────┐                ▼
 │ .pptx / .pdf     │──────► ┌──────────────────────┐        ┌───────────────────────┐
 │ (salta Whisper)  │        │ Ollama · Qwen 2.5 7B │───────►│ clases/<mat>/<clase>/ │
 └──────────────────┘        │ Chunking + Tree-     │        │   apuntes.md          │
                             │ Reduce               │        │   preguntas.json      │
                             │ keep_alive: 0 al fin │        └───────────┬───────────┘
                             └──────────────────────┘                    │
                                                                         │
        ┌────────────────────────────────────────────────────────────────┤
        │                                                                │
        ▼                                                                ▼
 ┌────────────────────────────┐   REST + SSE   ┌──────────────────────────────────────┐
 │ FastAPI  :8000             │◄──────────────►│ React 19 SPA (servida por FastAPI)   │
 │  ├─ JobManager (hilo +     │                │  ├─ Panel de procesamiento (SSE)     │
 │  │   data/.procesando.lock)│                │  ├─ Explorador de asignaturas        │
 │  ├─ ClassService           │                │  ├─ Editor Markdown (Ctrl/Cmd+S)     │
 │  ├─ StudyService (SM-2)    │                │  └─ Sesión de repaso SM-2            │
 │  └─ ExportService ─────────┼──► Notion API (bloques paginados)
 │                            │──► Telegram Bot (aviso al terminar)
 └────────────────────────────┘
```

El orquestador (`src/orchestrator.py`) es independiente de la interfaz: la API lo lanza en un hilo, le pasa callbacks de progreso y reenvía cada evento al navegador por SSE. El mismo orquestador funciona desde CLI (`src/procesar_clase.py`).

---

## Características

**Ingesta híbrida**
- Audio y vídeo local (MP4, MKV, MP3, M4A, WAV) o por URL. De las URLs solo se descarga la pista de audio con `yt-dlp`: 50–150 MB en vez de 1–3 GB de vídeo.
- `.pptx` (texto de diapositivas y notas del orador con `python-pptx`) y `.pdf` (texto por página con `pypdf`). Estos formatos se saltan Whisper y van directos al LLM. Si un PDF es un escaneo sin capa de texto, el job falla con un error explícito en vez de generar apuntes vacíos.
- Bookmarklet para extraer la URL del stream de Blackboard / Campus Virtual (ver más abajo).

**Síntesis que aguanta clases largas**
- La transcripción se trocea en bloques de ~9 000 caracteres, cada uno se resume por separado y los resúmenes se fusionan por pares en rondas sucesivas (Tree-Reduce) hasta que caben en el contexto del modelo.
- Si una fusión falla, se concatena ese par y el proceso sigue. Una clase de 3 horas no se pierde por un bloque problemático.
- Auditoría determinista posterior (`src/auditor.py`): cobertura de timestamps, bloques de código bien cerrados y orden cronológico.

**Jobs en segundo plano**
- Un único job activo a la vez, protegido con `data/.procesando.lock`.
- Progreso por fases (descarga, transcripción/extracción, síntesis, exportación) vía SSE.
- Si recargas la página (F5), el frontend consulta `GET /api/jobs/active` y se vuelve a suscribir al stream del job en curso.
- Cancelación desde la interfaz (`POST /api/jobs/{id}/cancel`).

**Editor de apuntes**
- Visor/editor Markdown integrado, guardado con `Ctrl+S` / `Cmd+S`.
- Escritura atómica (fichero temporal + `replace`) para no dejar un `apuntes.md` a medias si algo se corta.
- Exportación a Notion y aviso a Telegram con un botón desde la misma vista.

**Repaso activo con SM-2 Lite**
- Por cada clase se genera un banco de preguntas tipo test de 4 opciones con explicación.
- El frontend nunca recibe la respuesta correcta: la verificación se hace en el backend, que actualiza el intervalo de repaso de la pregunta y la racha diaria.
- Estado persistido en JSON con escritura atómica.

---

## Decisiones técnicas y trade-offs

### Por qué 100 % local

- **Privacidad:** las grabaciones contienen voces de profesores y compañeros. No salen del equipo.
- **Coste:** una clase de 2 horas son decenas de miles de tokens entre transcripción y síntesis. Con APIs de pago, procesar un curso entero cuesta dinero de forma recurrente. Aquí el coste marginal es la luz.
- **Sin cuotas:** no hay rate limits ni dependencia de que un proveedor cambie precios o modelos.

El precio que se paga: Qwen 2.5 7B no escribe como un modelo frontera, y una clase larga tarda bastante más que con una API. Para apuntes técnicos de estudio, compensa.

### Por qué Whisper en un subproceso y control explícito de la GPU

Whisper y Qwen no caben a la vez en 8 GB. Y liberar VRAM desde Python dentro del mismo proceso no es fiable: los frameworks cachean memoria y el recolector no la devuelve cuando tú quieres.

- **Whisper** se ejecuta como subproceso (`src/transcribir.py`). Cuando termina, el proceso muere y el sistema operativo recupera toda su memoria. Sin heurísticas.
- **Ollama** mantiene el modelo cargado 5 minutos por defecto. Tras cada síntesis se envía `keep_alive: 0` dentro de un `finally`, de modo que el modelo se descarga aunque la petición haya fallado.

Resultado: en un lote de varias clases, cada fase arranca con la GPU libre.

### Por qué el sistema de archivos en lugar de una base de datos

- La fuente de verdad son ficheros que se pueden abrir, editar, versionar con Git o copiar a otro equipo: `apuntes.md`, `transcripcion.txt`, `preguntas.json`.
- Es una aplicación monousuario y local. Un servidor de base de datos sería otra pieza que instalar y mantener sin aportar nada.
- La consistencia se resuelve con escrituras atómicas (temporal + `os.replace`) y un lockfile para la única operación pesada y concurrente.

El límite está claro: no escala a múltiples usuarios ni a consultas complejas. No es el objetivo.

### Por qué SSE en lugar de WebSockets

El flujo es unidireccional: el servidor informa del progreso y el cliente escucha. Las acciones del usuario (iniciar, cancelar) son peticiones REST normales.

- SSE funciona sobre HTTP estándar, lo soporta `EventSource` de forma nativa y no requiere un protocolo ni dependencias extra en FastAPI.
- La reconexión es trivial: si el cliente se cae, vuelve a pedir el job activo y se suscribe otra vez.

WebSockets solo tendría sentido si necesitáramos comunicación bidireccional de baja latencia, y no es el caso.

---

## Instalación

### Requisitos

| Componente | Versión | Notas |
|---|---|---|
| Python | 3.10+ | En el PATH (Windows) |
| Node.js | 18+ | Solo para compilar el frontend |
| FFmpeg | estable | Lo instalan los scripts de setup |
| Ollama | reciente | [ollama.com](https://ollama.com) |

- **macOS:** Apple Silicon (M1–M4). 16 GB recomendados para clases largas; con 8 GB funciona, pero más lento.
- **Windows:** GPU NVIDIA con CUDA 12. Con menos de 8 GB de VRAM, Whisper pasa a CPU en `int8`.

### macOS

```bash
git clone https://github.com/Fdemanna/lecture-flow.git
cd lecture-flow

bash scripts/setup_mac.sh            # crea venv/, instala dependencias y FFmpeg

cd frontend && npm install && npm run build && cd ..

ollama pull qwen2.5:7b

cp .env.example .env                 # opcional: credenciales de Notion/Telegram
```

Arrancar: doble clic en `Iniciar_Mac.command`. Abre `http://127.0.0.1:8000`.

### Windows

```bat
git clone https://github.com/Fdemanna/lecture-flow.git
cd lecture-flow

scripts\setup_windows.bat            :: crea venv_win\, verifica CUDA

cd frontend && npm install && npm run build && cd ..

ollama pull qwen2.5:7b

copy .env.example .env
```

Arrancar: doble clic en `Iniciar_Windows.vbs` (o `scripts\lanzador_win.bat`). Levanta Ollama si no está corriendo, arranca FastAPI y abre `http://127.0.0.1:8000`.

El modelo de Whisper (`large-v3-turbo`) se descarga solo la primera vez que se transcribe.

### Arranque manual y CLI

```bash
source venv/bin/activate             # Windows: venv_win\Scripts\activate.bat
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# Sin interfaz:
python src/procesar_clase.py "Bases de Datos" "Tema 3 - Normalización" ruta/clase.mp4
```

Para desarrollar el frontend con recarga en caliente: `cd frontend && npm run dev` (el proxy de Vite redirige `/api` a `:8000`).

### Variables de entorno (opcionales)

```env
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxx

TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=123456789
```

- **Notion:** crea una integración interna en [notion.so/my-integrations](https://www.notion.so/my-integrations), conéctala a la base de datos destino y copia el ID de la URL.
- **Telegram:** crea un bot con [@BotFather](https://t.me/BotFather), envíale `/start` y saca tu `chat_id` de `https://api.telegram.org/bot<TOKEN>/getUpdates`.

Sin estas variables la aplicación funciona igual; los botones de exportación devuelven un error claro indicando qué falta.

### Uso rápido

1. Elige asignatura y tema en el panel de procesamiento.
2. Sube un archivo (audio, vídeo, `.pptx`, `.pdf`) o pega una URL.
3. Sigue el progreso en directo. Puedes cerrar la pestaña: el job sigue en el servidor.
4. Abre la clase en el explorador para revisar y editar los apuntes.
5. Exporta a Notion si quieres, y repasa desde la sesión SM-2 los días siguientes.

### Bookmarklet para Blackboard

Crea un marcador con este código como URL. Con el vídeo de la clase reproduciéndose, púlsalo y la URL del stream queda en el portapapeles, lista para pegar en LectureFlow:

```javascript
javascript:(function(){const v=document.querySelector('video')||document.querySelector('source');if(v&&v.src){navigator.clipboard.writeText(v.src).then(()=>{alert('Enlace copiado al portapapeles:\n\n'+v.src.substring(0,100)+'...');});}else{alert('Dale al Play al vídeo primero y vuelve a pulsar este botón.');}})();
```

Los enlaces llevan un token de sesión que caduca. Si la descarga da 403, recarga la página de Blackboard y repite.

---

## Estructura del proyecto

```text
lecture-flow/
├── Iniciar_Mac.command            # Lanzador macOS (FastAPI + SPA en :8000)
├── Iniciar_Windows.vbs            # Lanzador Windows
├── requirements-mac.txt           # mlx-whisper, fastapi, python-pptx, pypdf…
├── requirements-win.txt           # faster-whisper, fastapi, python-pptx, pypdf…
├── .env.example
│
├── frontend/                      # React 19 + TypeScript + Vite + Tailwind v4
│   ├── vite.config.ts             # Proxy /api → 127.0.0.1:8000
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.css              # Tokens del tema oscuro
│   │   ├── services/api.ts        # Cliente REST tipado + EventSource
│   │   └── components/
│   │       ├── Sidebar.tsx        # Explorador de asignaturas y clases
│   │       ├── ProcessingPanel.tsx# Ingesta y progreso SSE
│   │       ├── NotesEditor.tsx    # Editor Markdown + export Notion/Telegram
│   │       └── PracticeSession.tsx# Repaso SM-2
│   └── dist/                      # Build servido por FastAPI (no versionado)
│
├── src/
│   ├── api/main.py                # Endpoints REST, SSE y montaje de la SPA
│   ├── services/
│   │   ├── class_service.py       # Asignaturas, clases y apuntes en disco
│   │   ├── job_service.py         # JobManager: hilo, lockfile, eventos SSE
│   │   ├── study_service.py       # Sesiones de repaso y verificación
│   │   └── export_service.py      # Notion y Telegram
│   ├── orchestrator.py            # Pipeline completo, independiente de la UI
│   ├── transcribir.py             # FFmpeg + Whisper (se ejecuta como subproceso)
│   ├── extractores_documentos.py  # .pptx y .pdf
│   ├── downloader.py              # yt-dlp, solo audio
│   ├── generar_apuntes.py         # Chunking, Tree-Reduce, keep_alive: 0
│   ├── study_engine.py            # SM-2 Lite y generación de preguntas
│   ├── auditor.py                 # Validación determinista de apuntes
│   ├── checkpoint_manager.py      # Reanudación de transcripciones largas
│   ├── cola_manager.py            # Cola de lotes con escritura atómica
│   ├── notion_exporter.py         # Markdown → bloques Notion, paginado
│   ├── notificador.py             # Telegram
│   └── procesar_clase.py          # Entrada CLI
│
├── app.py, views/                 # Interfaz Streamlit original (legacy, :8501)
│
├── clases/                        # Datos del usuario (no versionado)
│   └── <Asignatura>/<Clase>/
│       ├── transcripcion.txt
│       ├── apuntes.md
│       ├── preguntas.json
│       └── session_state.json
│
├── data/                          # Estado global de estudio y lockfile
├── scripts/                       # setup_mac.sh, setup_windows.bat, lanzador_win.bat
└── tests/
```

---

## Licencia

MIT. Ver [LICENSE](LICENSE).
