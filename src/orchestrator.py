"""
Motor de orquestación centralizado para LectureFlow.
Desacoplado de la interfaz de usuario (Streamlit) y reutilizable tanto por CLI
como por workers en segundo plano y la aplicación web.

Fases secuenciales:
  1. Transcripción (Whisper: CUDA en Windows / MLX en macOS Metal) con soporte Checkpoint.
  2. Síntesis pedagógica (Ollama Qwen 2.5) con descarga determinista de VRAM.
  3. Auditoría determinista de apuntes (validación de reglas Markdown y timestamps).
  4. Exportación opcional a Notion (sincronización con base de datos de apuntes).
  5. Notificación por Telegram (éxito o reporte de incidencias).
"""
from __future__ import annotations

import html
import logging
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional, Dict, Any, Union

from src.checkpoint_manager import (
    CheckpointManager,
    FASE_TRANSCRIBIENDO,
    FASE_SINTETIZANDO,
    FASE_EXPORTANDO,
    FASE_COMPLETADO,
)
from src.generar_apuntes import descargar_modelo_ollama, MODEL as MODELO_OLLAMA
from src.auditor import auditar_apuntes, ResultadoAuditoria
from src.notion_exporter import exportar_a_notion, notion_configurado
from src.notificador import (
    notificar_clase_completada,
    notificar_error,
    enviar_mensaje,
)
from src.cola_manager import ColaManager
from src.downloader import descargar_audio, es_url_remota

logger = logging.getLogger("orchestrator")

ROOT_DIR = Path(__file__).resolve().parent.parent
CARPETA_BASE = ROOT_DIR / "clases"
TIMEOUT_SUBPROCESO = 14400  # 4 horas para clases extensas (>2h)

ProgresoCallback = Callable[[str, int, str], None]
LineaCallback = Callable[[str], None]


def normalizar_nombre(texto: str) -> str:
    """Elimina caracteres problemáticos para nombres de carpetas en el sistema de archivos."""
    caracteres_validos = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    limpio = "".join(c for c in texto if c in caracteres_validos)
    return limpio.strip().replace(" ", "_")


def es_ruta_segura(ruta_destino: Union[str, Path], base: Union[str, Path] = CARPETA_BASE) -> bool:
    """Valida que la ruta pertenezca estrictamente al subárbol permitido."""
    base_real = os.path.realpath(str(base))
    candidata_real = os.path.realpath(str(ruta_destino))
    return candidata_real.startswith(base_real + os.sep) or candidata_real == base_real


class PipelineOrchestrator:
    """Orquestador desacoplado del pipeline de procesamiento de clases.

    Parámetros
    ----------
    callback_progreso:
        Función opcional ``(fase: str, progreso: int, mensaje: str) -> None``.
    callback_linea:
        Función opcional ``(linea: str) -> None`` que recibe cada línea de stdout
        emitida en tiempo real por los subprocesos de Whisper u Ollama.
    """

    def __init__(
        self,
        callback_progreso: Optional[ProgresoCallback] = None,
        callback_linea: Optional[LineaCallback] = None,
    ) -> None:
        self.callback_progreso = callback_progreso
        self.callback_linea = callback_linea

    def _emitir_progreso(self, fase: str, porcentaje: int, mensaje: str) -> None:
        if self.callback_progreso:
            try:
                self.callback_progreso(fase, porcentaje, mensaje)
            except Exception as e:
                print(f"[ORCHESTRATOR] Advertencia en callback_progreso: {e}", file=sys.stderr)

    def _emitir_linea(self, linea: str) -> None:
        if self.callback_linea:
            try:
                self.callback_linea(linea)
            except Exception as e:
                print(f"[ORCHESTRATOR] Advertencia en callback_linea: {e}", file=sys.stderr)
        else:
            print(linea, end="", flush=True)

    def _ejecutar_subproceso_stream(self, comando: list[str], timeout: int = TIMEOUT_SUBPROCESO) -> None:
        """Ejecuta un subproceso leyendo stdout en tiempo real y garantizando

        el cierre y terminación forzosa en caso de fallo o interrupción.
        """
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        t_inicio = time.monotonic()
        try:
            while True:
                linea = proceso.stdout.readline() if proceso.stdout else ""
                if not linea and proceso.poll() is not None:
                    break
                if linea:
                    self._emitir_linea(linea)
                if timeout and (time.monotonic() - t_inicio > timeout):
                    proceso.kill()
                    raise TimeoutError(f"Subproceso excedió el tiempo límite de {timeout}s: {' '.join(comando[:3])}")
        except Exception:
            if proceso.poll() is None:
                proceso.kill()
            raise
        finally:
            if proceso.stdout:
                try:
                    proceso.stdout.close()
                except OSError:
                    pass

        codigo = proceso.wait()
        if codigo != 0:
            raise subprocess.CalledProcessError(codigo, comando)

    def procesar_clase(
        self,
        video_path: Union[str, Path],
        materia: str,
        nombre_clase: str,
        modo_reanudacion: bool = False,
        exportar_notion: bool = True,
        solo_apuntes: bool = False,
        forzar_transcripcion: bool = False,
    ) -> Dict[str, Any]:
        """Ejecuta el pipeline completo de una clase de principio a fin.

        Devuelve un diccionario con los resultados y metadatos de la sesión.
        """
        t_inicio_total = time.monotonic()
        materia_clean = normalizar_nombre(materia)
        clase_clean = normalizar_nombre(nombre_clase)
        directorio_destino = CARPETA_BASE / materia_clean / clase_clean

        if not es_ruta_segura(directorio_destino):
            raise ValueError(f"Ruta de destino no segura o fuera del directorio base: {directorio_destino}")

        directorio_destino.mkdir(parents=True, exist_ok=True)
        ruta_transcripcion = directorio_destino / "transcripcion.txt"
        ruta_apuntes = directorio_destino / "apuntes.md"

        video_path_str_raw = str(video_path).strip()

        # ---------------------------------------------------------------
        # FASE 0: Descarga de Audio (solo si video_path es URL remota)
        # ---------------------------------------------------------------
        if es_url_remota(video_path_str_raw) and not solo_apuntes:
            self._emitir_progreso("descarga", 2, "Fase 0/4: Descargando audio desde URL remota…")
            self._emitir_linea(f"[DESCARGA] URL detectada: {video_path_str_raw}\n")
            try:
                ruta_descargada = descargar_audio(
                    url=video_path_str_raw,
                    directorio_destino=directorio_destino,
                    nombre_base="audio_original",
                    callback_progreso=self.callback_progreso,
                )
                vid_path_str = str(ruta_descargada)
                self._emitir_progreso("descarga", 14, f"Audio descargado: {ruta_descargada.name}")
                self._emitir_linea(f"[DESCARGA] Guardado en: {ruta_descargada}\n")
            except RuntimeError as exc_dl:
                raise RuntimeError(f"Descarga fallida: {exc_dl}") from exc_dl
        else:
            vid_path_str = str(Path(video_path_str_raw).resolve()) if video_path_str_raw else ""

        # Mover o copiar el archivo local a la carpeta de la clase si no está allí
        if vid_path_str and os.path.exists(vid_path_str) and not solo_apuntes:
            archivo_en_carpeta = directorio_destino / Path(vid_path_str).name
            if not archivo_en_carpeta.exists():
                self._emitir_linea(f"-> Copiando archivo multimedia a carpeta de destino: {archivo_en_carpeta.name}\n")
                shutil.copy2(vid_path_str, archivo_en_carpeta)
                vid_path_str = str(archivo_en_carpeta)

        cp = CheckpointManager(str(directorio_destino), vid_path_str)

        try:
            # ---------------------------------------------------------------
            # FASE 1: Transcripción (Whisper)
            # ---------------------------------------------------------------
            transcripcion_existe = ruta_transcripcion.exists() and ruta_transcripcion.stat().st_size > 0

            if solo_apuntes:
                if not transcripcion_existe:
                    raise FileNotFoundError(f"Modo solo_apuntes solicitado pero no existe: {ruta_transcripcion}")
                self._emitir_progreso("transcripcion", 50, "Paso 1/2 omitido: usando transcripcion.txt existente.")
                self._emitir_linea(f"[INFO] Reutilizando transcripción existente ({ruta_transcripcion.stat().st_size:,} bytes)\n")
            elif transcripcion_existe and not forzar_transcripcion and not modo_reanudacion and not cp.existe_sesion_previa():
                self._emitir_progreso("transcripcion", 50, "Paso 1/2 omitido: Transcripción previa detectada.")
                self._emitir_linea(f"[INFO] Se reutiliza 'transcripcion.txt' ({ruta_transcripcion.name})\n")
            else:
                self._emitir_progreso("transcripcion", 15, "Paso 1/4: Extrayendo audio y transcribiendo con Whisper...")
                cmd_trans = [
                    sys.executable, "-u",
                    str(ROOT_DIR / "src" / "transcribir.py"),
                    vid_path_str,
                    str(ruta_transcripcion),
                ]
                if modo_reanudacion or cp.existe_sesion_previa():
                    cmd_trans.append("--reanudar")
                    self._emitir_progreso("transcripcion", 20, "Reanudando transcripción desde último checkpoint...")
                else:
                    cp.inicializar_nueva_sesion()

                self._ejecutar_subproceso_stream(cmd_trans)
                self._emitir_progreso("transcripcion", 50, "Transcripción completada con éxito.")

            # ---------------------------------------------------------------
            # FASE 2: Síntesis Pedagógica con Qwen 2.5 (Ollama)
            # ---------------------------------------------------------------
            self._emitir_progreso("sintesis", 55, "Paso 2/4: Sintetizando apuntes estructurados con Qwen 2.5...")
            cp.avanzar_fase(FASE_SINTETIZANDO)

            cmd_apuntes = [
                sys.executable, "-u",
                str(ROOT_DIR / "src" / "generar_apuntes.py"),
                str(ruta_transcripcion),
                str(ruta_apuntes),
            ]
            try:
                self._ejecutar_subproceso_stream(cmd_apuntes)
            finally:
                # Descarga determinista de VRAM para evitar OOM con procesos concurrentes o posteriores
                descargar_modelo_ollama(MODELO_OLLAMA)

            self._emitir_progreso("sintesis", 80, "Síntesis pedagógica completada.")

            # ---------------------------------------------------------------
            # FASE 3: Auditoría Determinista de Calidad
            # ---------------------------------------------------------------
            self._emitir_progreso("auditoria", 82, "Paso 3/4: Auditando coherencia y calidad de apuntes...")
            texto_apuntes = ""
            if ruta_apuntes.exists():
                with open(ruta_apuntes, "r", encoding="utf-8") as f:
                    texto_apuntes = f.read()

            res_auditoria: Optional[ResultadoAuditoria] = None
            if texto_apuntes:
                res_auditoria = auditar_apuntes(texto_apuntes)
                self._emitir_linea("\n" + "="*50 + "\n[AUDITORÍA DETERMINISTA]\n" + "="*50 + "\n")
                self._emitir_linea(f"  Válido: {res_auditoria.es_valido}\n")
                self._emitir_linea(f"  Timestamps detectados: {res_auditoria.timestamps_detectados}\n")
                self._emitir_linea(f"  Cobertura de términos: {res_auditoria.cobertura_terminos:.0%}\n")
                if res_auditoria.errores:
                    self._emitir_linea(f"  Errores críticos: {len(res_auditoria.errores)}\n")
                if res_auditoria.advertencias:
                    self._emitir_linea(f"  Advertencias: {len(res_auditoria.advertencias)}\n")
            self._emitir_progreso("auditoria", 90, "Auditoría completada.")

            # ---------------------------------------------------------------
            # ---------------------------------------------------------------
            # FASE 4: Exportación Opcional a Notion
            # ---------------------------------------------------------------
            url_notion: Optional[str] = None
            error_notion: Optional[str] = None

            if exportar_notion and texto_apuntes:
                self._emitir_progreso("exportacion_notion", 92, "Paso 4/4: Sincronizando con base de datos de Notion...")
                cp.avanzar_fase(FASE_EXPORTANDO)
                try:
                    url_notion = exportar_a_notion(clase_clean, materia_clean, texto_apuntes)
                    self._emitir_linea(f"\n[NOTION] Exportado exitosamente: {url_notion}\n")
                    self._emitir_progreso("exportacion_notion", 98, "Sincronizado con Notion.")
                except Exception as exc_notion:
                    error_notion = str(exc_notion)
                    logger.error(
                        "Error al exportar a Notion para la clase '%s': %s",
                        clase_clean, error_notion, exc_info=True
                    )
                    self._emitir_linea(f"\n[NOTION ERROR] Falló la exportación a Notion: {error_notion}\n")
                    self._emitir_progreso("exportacion_notion", 95, f"⚠️ Error en Notion: {error_notion[:60]}")

            # Finalizar sesión de checkpoint
            cp.marcar_completado()

            # ---------------------------------------------------------------
            # FASE 5: Notificación Telegram y Métricas
            # ---------------------------------------------------------------
            duracion_seg = int(time.monotonic() - t_inicio_total)
            duracion_str = f"{duracion_seg // 60}m {duracion_seg % 60}s"

            if error_notion:
                # Si falló Notion: no enviar mensaje triunfal general.
                # Notificar advertencia específica de fallo de Notion por Telegram.
                detalle_limpio = html.escape(error_notion[:300])
                msg_aviso = (
                    f"✅ Clase procesada localmente pero ⚠️ falló la exportación a Notion: {detalle_limpio}"
                )
                enviar_mensaje(msg_aviso)
                self._emitir_progreso(
                    "completado",
                    100,
                    f"Clase '{clase_clean}' procesada localmente (⚠️ falló Notion)."
                )
            else:
                notificar_clase_completada(
                    nombre_clase=clase_clean.replace("_", " "),
                    duracion=duracion_str,
                    url_notion=url_notion,
                )
                self._emitir_progreso("completado", 100, f"¡Clase '{clase_clean}' completada en {duracion_str}!")

            return {
                "exito": True,
                "materia": materia_clean,
                "nombre_clase": clase_clean,
                "directorio": str(directorio_destino),
                "ruta_transcripcion": str(ruta_transcripcion),
                "ruta_apuntes": str(ruta_apuntes),
                "url_notion": url_notion,
                "error_notion": error_notion,
                "duracion": duracion_str,
                "duracion_seg": duracion_seg,
                "auditoria": res_auditoria,
                "error": None,
            }

        except Exception as exc:
            msg_error = str(exc)
            self._emitir_progreso("error", 0, f"Fallo en pipeline: {msg_error}")
            notificar_error(
                contexto=f"Clase: {clase_clean.replace('_', ' ')}",
                detalle=msg_error[:300],
            )
            return {
                "exito": False,
                "materia": materia_clean,
                "nombre_clase": clase_clean,
                "directorio": str(directorio_destino),
                "ruta_transcripcion": str(ruta_transcripcion),
                "ruta_apuntes": str(ruta_apuntes),
                "url_notion": None,
                "error_notion": None,
                "duracion": None,
                "duracion_seg": int(time.monotonic() - t_inicio_total),
                "auditoria": None,
                "error": msg_error,
            }

    def procesar_trabajo_cola(
        self,
        trabajo: dict,
        exportar_notion: Optional[bool] = None,
        cola_manager: Optional[ColaManager] = None,
    ) -> bool:
        """Procesa de forma atómica un trabajo de la cola persistente.

        Actualiza su estado a 'en_progreso' y posteriormente a 'completado' o 'error'.
        """
        if exportar_notion is None:
            exportar_notion = notion_configurado()

        trabajo_id = trabajo.get("id")
        video_path = trabajo.get("video_path", "")
        materia = trabajo.get("materia", "General")
        nombre_clase = trabajo.get("nombre_clase", "Clase")
        directorio_clase = trabajo.get("directorio_clase", "")

        if cola_manager and trabajo_id:
            cola_manager.marcar_en_progreso(trabajo_id)

        # Detectar si ya tenía checkpoint parcial
        modo_reanudar = False
        if directorio_clase and os.path.exists(directorio_clase):
            cp = CheckpointManager(directorio_clase, video_path)
            if cp.existe_sesion_previa():
                modo_reanudar = True

        resultado = self.procesar_clase(
            video_path=video_path,
            materia=materia,
            nombre_clase=nombre_clase,
            modo_reanudacion=modo_reanudar,
            exportar_notion=exportar_notion,
        )

        if resultado["exito"]:
            if cola_manager and trabajo_id:
                cola_manager.marcar_completado(trabajo_id)
            return True
        else:
            if cola_manager and trabajo_id:
                cola_manager.marcar_error(trabajo_id, str(resultado["error"])[:200])
            return False
