"""Aplicación principal FastAPI para la arquitectura desacoplada de LectureFlow."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.services.class_service import (
    obtener_arbol_clases,
    renombrar_materia,
    eliminar_materia,
    leer_apuntes_clase,
    guardar_apuntes_clase,
)
from src.services.study_service import (
    obtener_estadisticas_estudio,
    obtener_preguntas_sesion,
    verificar_y_registrar_respuesta,
)
from src.services.export_service import (
    exportar_clase_a_notion,
    notificar_clase_por_telegram,
)
from src.services.job_service import job_manager

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

app = FastAPI(
    title="LectureFlow API",
    version="1.0.0",
    description="API REST desacoplada para la suite académica LectureFlow.",
)

# Configuración de CORS para el frontend (Vite/React en puerto 5173)
ORIGENES_PERMITIDOS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RenombrarMateriaRequest(BaseModel):
    nuevo_nombre: str = Field(..., min_length=1, description="Nuevo nombre para la asignatura")


dist_dir = ROOT_DIR / "frontend" / "dist"


@app.get("/")
def raiz():
    """Ruta raíz que sirve la SPA React si está compilada, o el estado de la API."""
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        return FileResponse(dist_dir / "index.html")
    return {
        "app": "LectureFlow API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/api/health")
def obtener_salud_sistema() -> Dict[str, Any]:
    """Comprueba el estado de salud del sistema y si existe un procesamiento en curso."""
    ruta_lock = ROOT_DIR / "data" / ".procesando.lock"
    lockfile_presente = ruta_lock.is_file()
    clase_en_proceso: Optional[str] = None

    if lockfile_presente:
        try:
            clase_en_proceso = ruta_lock.read_text(encoding="utf-8").strip() or "Proceso activo"
        except Exception:
            clase_en_proceso = "Proceso activo"

    return {
        "status": "ok",
        "procesando": lockfile_presente,
        "clase_en_proceso": clase_en_proceso,
        "lockfile_presente": lockfile_presente,
    }


@app.get("/api/classes", response_model=List[Dict[str, Any]])
def listar_clases() -> List[Dict[str, Any]]:
    """Devuelve el árbol jerárquico de asignaturas y clases con sus artefactos."""
    return obtener_arbol_clases(root_dir=ROOT_DIR)


@app.patch("/api/classes/{materia}")
def api_renombrar_materia(materia: str, body: RenombrarMateriaRequest) -> Dict[str, Any]:
    """Renombra una materia existente."""
    try:
        return renombrar_materia(
            root_dir=ROOT_DIR,
            nombre_actual=materia,
            nuevo_nombre=body.nuevo_nombre,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


@app.delete("/api/classes/{materia}")
def api_eliminar_materia(materia: str) -> Dict[str, Any]:
    """Elimina permanentemente una materia y su contenido."""
    try:
        return eliminar_materia(
            root_dir=ROOT_DIR,
            nombre_materia=materia,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


class GuardarApuntesRequest(BaseModel):
    contenido: str = Field(..., description="Contenido Markdown de los apuntes")


@app.get("/api/classes/{materia}/{clase}/notes")
def api_leer_apuntes(materia: str, clase: str) -> Dict[str, Any]:
    """Lee el archivo de apuntes de una clase específica."""
    try:
        resultado = leer_apuntes_clase(root_dir=ROOT_DIR, materia=materia, clase=clase)
        if not resultado["existe"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La clase '{clase}' no dispone de archivo de apuntes.",
            )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


@app.put("/api/classes/{materia}/{clase}/notes")
def api_guardar_apuntes(materia: str, clase: str, body: GuardarApuntesRequest) -> Dict[str, Any]:
    """Guarda modificaciones en los apuntes Markdown de una clase."""
    try:
        return guardar_apuntes_clase(
            root_dir=ROOT_DIR,
            materia=materia,
            clase=clase,
            contenido=body.contenido,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


class NotificarTelegramRequest(BaseModel):
    url_notion: Optional[str] = Field(None, description="URL opcional de Notion para adjuntar en la notificación")


@app.post("/api/classes/{materia}/{clase}/export/notion")
def api_exportar_notion(materia: str, clase: str) -> Dict[str, Any]:
    """Exporta los apuntes Markdown de la clase a Notion."""
    try:
        return exportar_clase_a_notion(
            root_dir=ROOT_DIR,
            materia=materia,
            clase=clase,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


@app.post("/api/classes/{materia}/{clase}/export/telegram")
def api_notificar_telegram(
    materia: str,
    clase: str,
    body: Optional[NotificarTelegramRequest] = None,
) -> Dict[str, Any]:
    """Envía notificación de clase a Telegram."""
    try:
        url_notion = body.url_notion if body else None
        return notificar_clase_por_telegram(
            root_dir=ROOT_DIR,
            materia=materia,
            clase=clase,
            url_notion=url_notion,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")


@app.get("/api/study/stats")
def obtener_estadisticas() -> Dict[str, Any]:
    """Devuelve las estadísticas acumuladas de estudio (racha, XP y estado SM-2)."""
    return obtener_estadisticas_estudio()


class ResponderPreguntaRequest(BaseModel):
    question_id: str = Field(..., description="ID de la pregunta")
    selected_option: int = Field(..., ge=0, le=3, description="Índice de la opción seleccionada (0 a 3)")


@app.get("/api/study/due")
def api_preguntas_pendientes(limit: int = 5) -> List[Dict[str, Any]]:
    """Devuelve lote de preguntas prioritarias para repaso espaciado (sin respuestas correctas)."""
    return obtener_preguntas_sesion(root_dir=ROOT_DIR, limite=max(1, min(limit, 50)))


@app.post("/api/study/answer")
def api_responder_pregunta(body: ResponderPreguntaRequest) -> Dict[str, Any]:
    """Evalúa la respuesta de una pregunta, actualiza SM-2 Lite y la racha diaria."""
    try:
        return verificar_y_registrar_respuesta(
            question_id=body.question_id,
            selected_option=body.selected_option,
            root_dir=ROOT_DIR,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error inesperado: {e}")



# =============================================================================
# ENDPOINTS DE JOBS DE PROCESAMIENTO EN SEGUNDO PLANO Y SSE
# =============================================================================

@app.post("/api/jobs")
async def api_crear_job(
    request: Request,
    materia: Optional[str] = Form(None),
    tema: Optional[str] = Form(None),
    tipo_origen: Optional[str] = Form("url"),
    url: Optional[str] = Form(None),
    archivo: Optional[UploadFile] = File(None),
    modo_reanudacion: bool = Form(False),
    exportar_notion: bool = Form(True),
    solo_apuntes: bool = Form(False),
    forzar_transcripcion: bool = Form(False),
) -> Dict[str, Any]:
    """Inicia un procesamiento asíncrono en segundo plano (URL o archivo .pptx/.mp4)."""
    activo = job_manager.obtener_job_activo()
    if activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Ya existe un procesamiento en curso.", "active_job": activo},
        )

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            materia = (body.get("materia") or "").strip()
            tema = (body.get("tema") or "").strip()
            tipo_origen = body.get("tipo_origen") or "url"
            origen_final = (body.get("origen") or body.get("url") or "").strip()
            opciones = body.get("opciones") or {}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payload JSON inválido: {e}")
    else:
        materia = (materia or "").strip()
        tema = (tema or "").strip()
        origen_final = ""

        if archivo and archivo.filename:
            carpeta_uploads = ROOT_DIR / "data" / "uploads"
            carpeta_uploads.mkdir(parents=True, exist_ok=True)
            ruta_guardado = carpeta_uploads / archivo.filename
            contenido_bytes = await archivo.read()
            ruta_guardado.write_bytes(contenido_bytes)
            origen_final = str(ruta_guardado)
            tipo_origen = "upload"
        else:
            origen_final = (url or "").strip()

        opciones = {
            "modo_reanudacion": modo_reanudacion,
            "exportar_notion": exportar_notion,
            "solo_apuntes": solo_apuntes,
            "forzar_transcripcion": forzar_transcripcion,
        }

    if not materia or not tema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tanto la asignatura (materia) como el tema son campos obligatorios.",
        )

    if not origen_final:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes especificar una URL remota o adjuntar un archivo multimedia/PowerPoint.",
        )

    try:
        return job_manager.iniciar_job(
            materia=materia,
            tema=tema,
            origen=origen_final,
            tipo_origen=tipo_origen or "url",
            opciones=opciones,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "active_job": job_manager.obtener_job_activo()},
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al iniciar job: {e}")


@app.get("/api/jobs/active")
def api_obtener_job_activo() -> Optional[Dict[str, Any]]:
    """Devuelve el estado del job activo o null si el sistema está libre."""
    return job_manager.obtener_job_activo()


@app.get("/api/jobs/{job_id}/events")
async def api_eventos_job(job_id: str):
    """Canal Server-Sent Events (SSE) para telemetría de progreso en tiempo real."""
    return StreamingResponse(
        job_manager.suscribir_eventos(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/jobs/{job_id}/cancel")
def api_cancelar_job(job_id: str) -> Dict[str, Any]:
    """Cancela un job activo y libera el lockfile."""
    exito = job_manager.cancelar_job(job_id)
    if not exito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró un job activo con id '{job_id}'.",
        )
    return {"status": "cancelled", "job_id": job_id, "message": "Procesamiento cancelado y bloqueo liberado."}


# =============================================================================
# MONTAJE DE LA SPA (REACT FRONTEND EN DIST)
# =============================================================================

dist_dir = ROOT_DIR / "frontend" / "dist"
if dist_dir.exists():
    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Endpoint no encontrado")
        archivo = dist_dir / full_path
        if archivo.exists() and archivo.is_file():
            return FileResponse(archivo)
        return FileResponse(dist_dir / "index.html")



