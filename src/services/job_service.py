"""Servicio de gestión de Jobs en segundo plano con Server-Sent Events (SSE) para LectureFlow."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from src.orchestrator import PipelineOrchestrator

logger = logging.getLogger("job_service")
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RUTA_LOCK = ROOT_DIR / "data" / ".procesando.lock"


class JobManager:
    """Gestor singleton para orquestar la ejecución asíncrona de clases en hilos de fondo."""

    _instance: Optional[JobManager] = None

    def __new__(cls) -> JobManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self) -> None:
        self._lock = threading.Lock()
        self._active_job: Optional[Dict[str, Any]] = None
        self._worker_thread: Optional[threading.Thread] = None
        # Mapeo de job_id -> conjunto de colas asyncio
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # Historial reciente de jobs finalizados
        self._job_history: Dict[str, Dict[str, Any]] = {}

    def obtener_job_activo(self) -> Optional[Dict[str, Any]]:
        """Devuelve el estado del job en curso o detecta si existe un lockfile externo."""
        with self._lock:
            if self._active_job and self._active_job.get("status") == "running":
                # Retornar copia limpia sin objetos internos
                return {
                    k: v for k, v in self._active_job.items()
                    if k not in ("subscribers",)
                }

        # Comprobar si hay un bloqueo originado externamente (ej. Streamlit)
        if RUTA_LOCK.exists():
            try:
                contenido = RUTA_LOCK.read_text(encoding="utf-8").strip() or "Proceso en curso"
            except Exception:
                contenido = "Proceso en curso"

            partes = contenido.split(" / ")
            materia = partes[0].strip() if len(partes) > 0 else "General"
            tema = partes[1].strip() if len(partes) > 1 else contenido

            return {
                "job_id": "external",
                "materia": materia,
                "tema": tema,
                "status": "running",
                "phase": "procesando_externo",
                "progress": 50,
                "message": f"Procesamiento en curso en interfaz Streamlit ({contenido})",
                "created_at": datetime.datetime.now().isoformat(),
                "es_externo": True,
            }

        return None

    def _broadcast(self, job_id: str, evento: Dict[str, Any]) -> None:
        """Emite un evento a todos los suscriptores conectados al SSE."""
        colas = list(self._subscribers.get(job_id, set()))
        for q in colas:
            try:
                # Usar call_soon_threadsafe si hay un bucle activo o put_nowait directo
                q.put_nowait(evento)
            except Exception as e:
                logger.debug("Fallo al entregar evento a suscriptor: %s", e)

    def iniciar_job(
        self,
        materia: str,
        tema: str,
        origen: str,
        tipo_origen: str,
        opciones: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Inicia una tarea de procesamiento en un hilo secundario y emite telemetría."""
        with self._lock:
            if self._active_job and self._active_job.get("status") == "running":
                raise RuntimeError(
                    f"Ya existe una tarea activa: {self._active_job.get('materia')} / {self._active_job.get('tema')}"
                )

            if RUTA_LOCK.exists():
                raise RuntimeError("El archivo de bloqueo data/.procesando.lock ya está activo.")

            job_id = uuid.uuid4().hex[:10]
            opciones_limpias = opciones or {}

            # Crear lockfile
            RUTA_LOCK.parent.mkdir(parents=True, exist_ok=True)
            RUTA_LOCK.write_text(f"{materia} / {tema}", encoding="utf-8")

            job_data: Dict[str, Any] = {
                "job_id": job_id,
                "materia": materia,
                "tema": tema,
                "origen": origen,
                "tipo_origen": tipo_origen,
                "status": "running",
                "phase": "iniciando",
                "progress": 1,
                "message": "Inicializando pipeline de procesamiento...",
                "created_at": datetime.datetime.now().isoformat(),
                "completed_at": None,
                "error": None,
            }

            self._active_job = job_data
            self._subscribers[job_id] = set()

            # Lanzar hilo secundario
            self._worker_thread = threading.Thread(
                target=self._ejecutar_pipeline_hilo,
                args=(job_id, materia, tema, origen, opciones_limpias),
                daemon=True,
                name=f"Worker-{job_id}",
            )
            self._worker_thread.start()

            return {
                "job_id": job_id,
                "status": "running",
                "materia": materia,
                "tema": tema,
                "message": "Procesamiento iniciado con éxito.",
            }

    def _ejecutar_pipeline_hilo(
        self,
        job_id: str,
        materia: str,
        tema: str,
        origen: str,
        opciones: Dict[str, Any],
    ) -> None:
        """Ejecuta el PipelineOrchestrator en segundo plano y actualiza el estado."""
        def callback_progreso(fase: str, progreso: int, mensaje: str) -> None:
            with self._lock:
                if self._active_job and self._active_job.get("job_id") == job_id:
                    self._active_job["phase"] = fase
                    self._active_job["progress"] = progreso
                    self._active_job["message"] = mensaje

            self._broadcast(job_id, {
                "job_id": job_id,
                "status": "running",
                "phase": fase,
                "progress": progreso,
                "message": mensaje,
            })

        try:
            callback_progreso("inicio", 3, f"Preparando ingesta para '{tema}'...")

            orquestador = PipelineOrchestrator(
                callback_progreso=callback_progreso,
                callback_linea=None,
            )

            # Ejecución del pipeline
            resultado = orquestador.procesar_clase(
                video_path=origen,
                materia=materia,
                nombre_clase=tema,
                modo_reanudacion=opciones.get("modo_reanudacion", False),
                exportar_notion=opciones.get("exportar_notion", True),
                solo_apuntes=opciones.get("solo_apuntes", False),
                forzar_transcripcion=opciones.get("forzar_transcripcion", False),
            )

            with self._lock:
                if self._active_job and self._active_job.get("job_id") == job_id:
                    self._active_job["status"] = "completed"
                    self._active_job["phase"] = "completado"
                    self._active_job["progress"] = 100
                    self._active_job["message"] = "Clase procesada y sintetizada con éxito."
                    self._active_job["completed_at"] = datetime.datetime.now().isoformat()
                    self._active_job["resultado"] = resultado
                    self._job_history[job_id] = dict(self._active_job)

            self._broadcast(job_id, {
                "job_id": job_id,
                "status": "completed",
                "phase": "completado",
                "progress": 100,
                "message": "Clase procesada y sintetizada con éxito.",
            })

        except Exception as exc:
            logger.error("Fallo durante el procesamiento del job %s: %s", job_id, exc, exc_info=True)
            with self._lock:
                if self._active_job and self._active_job.get("job_id") == job_id:
                    self._active_job["status"] = "failed"
                    self._active_job["phase"] = "error"
                    self._active_job["error"] = str(exc)
                    self._active_job["message"] = f"Error en procesamiento: {exc}"
                    self._active_job["completed_at"] = datetime.datetime.now().isoformat()
                    self._job_history[job_id] = dict(self._active_job)

            self._broadcast(job_id, {
                "job_id": job_id,
                "status": "failed",
                "phase": "error",
                "progress": self._active_job.get("progress", 0) if self._active_job else 0,
                "message": f"Error: {exc}",
                "error": str(exc),
            })

        finally:
            # Liberar cerrojo en disco
            try:
                RUTA_LOCK.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Fallo al eliminar lockfile tras finalizar job: %s", e)

            with self._lock:
                if self._active_job and self._active_job.get("job_id") == job_id:
                    # Dejar referencia en historial pero limpiar job activo
                    self._active_job = None

    async def suscribir_eventos(self, job_id: str) -> AsyncGenerator[str, None]:
        """Generador asíncrono para Server-Sent Events (SSE)."""
        queue: asyncio.Queue = asyncio.Queue()

        with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add(queue)

            # Estado inicial actual
            estado_actual = None
            if self._active_job and self._active_job.get("job_id") == job_id:
                estado_actual = {
                    "job_id": job_id,
                    "status": self._active_job.get("status"),
                    "phase": self._active_job.get("phase"),
                    "progress": self._active_job.get("progress"),
                    "message": self._active_job.get("message"),
                }
            elif job_id in self._job_history:
                hist = self._job_history[job_id]
                estado_actual = {
                    "job_id": job_id,
                    "status": hist.get("status"),
                    "phase": hist.get("phase"),
                    "progress": hist.get("progress"),
                    "message": hist.get("message"),
                }

        if estado_actual:
            yield f"data: {json.dumps(estado_actual, ensure_ascii=False)}\n\n"
            if estado_actual.get("status") in ("completed", "failed", "cancelled"):
                return

        try:
            while True:
                try:
                    # Espera con timeout para enviar keep-alive ping
                    evento = await asyncio.wait_for(queue.get(), timeout=12.0)
                    yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

                    if evento.get("status") in ("completed", "failed", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            with self._lock:
                if job_id in self._subscribers and queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)
                    if not self._subscribers[job_id] and (not self._active_job or self._active_job.get("job_id") != job_id):
                        del self._subscribers[job_id]

    def cancelar_job(self, job_id: str) -> bool:
        """Cancela el job activo si coincide con el job_id y libera el lockfile."""
        with self._lock:
            if self._active_job and self._active_job.get("job_id") == job_id:
                self._active_job["status"] = "cancelled"
                self._active_job["phase"] = "cancelado"
                self._active_job["message"] = "Procesamiento cancelado por el usuario."
                self._active_job["completed_at"] = datetime.datetime.now().isoformat()
                self._job_history[job_id] = dict(self._active_job)
                self._active_job = None

                try:
                    RUTA_LOCK.unlink(missing_ok=True)
                except Exception:
                    pass

                self._broadcast(job_id, {
                    "job_id": job_id,
                    "status": "cancelled",
                    "phase": "cancelado",
                    "progress": 0,
                    "message": "Procesamiento cancelado por el usuario.",
                })
                return True

        # Si el job_id es "external" o el lockfile existe, permitir liberar el lockfile
        if RUTA_LOCK.exists():
            try:
                RUTA_LOCK.unlink(missing_ok=True)
                return True
            except Exception:
                pass

        return False


# Singleton global
job_manager = JobManager()
