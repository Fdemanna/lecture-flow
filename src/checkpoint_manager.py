"""
Módulo de gestión de checkpoints para LectureFlow.

Persiste el estado de cada sesión de procesamiento en un archivo
``session_state.json`` ubicado en la carpeta de salida de la clase.
Permite reanudar la transcripción desde el último segmento guardado
tras una interrupción abrupta (apagón, cierre forzado, crash).

Esquema del estado persistido
------------------------------
{
    "video_path": "ruta/al/archivo",
    "fase_actual": "transcribiendo | sintetizando | exportando | completado",
    "ultimo_timestamp": 0.0,
    "segmentos_transcritos": [...],
    "fecha_actualizacion": "ISO-8601"
}
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CHECKPOINT_FILENAME = "session_state.json"

# Guardar checkpoint cada N segmentos para evitar degradación de I/O excesiva
CHECKPOINT_INTERVAL_SEGMENTOS = 10

# Fases válidas del pipeline
FASE_TRANSCRIBIENDO = "transcribiendo"
FASE_SINTETIZANDO = "sintetizando"
FASE_EXPORTANDO = "exportando"
FASE_COMPLETADO = "completado"


# ---------------------------------------------------------------------------
# Estructura de estado
# ---------------------------------------------------------------------------

def _estado_inicial(video_path: str) -> dict:
    """Devuelve un diccionario con los valores por defecto del estado."""
    return {
        "video_path": str(Path(video_path).resolve()) if video_path else "",
        "fase_actual": FASE_TRANSCRIBIENDO,
        "ultimo_timestamp": 0.0,
        "segmentos_transcritos": [],
        "fecha_actualizacion": _ahora_iso(),
    }


def _ahora_iso() -> str:
    """Devuelve el instante actual en formato ISO-8601 con timezone UTC."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class CheckpointManager:
    """Gestiona la lectura, escritura y validación del archivo de estado de sesión.

    Parámetros
    ----------
    directorio_salida:
        Carpeta de la clase donde se almacena ``session_state.json``.
    video_path:
        Ruta al archivo multimedia de la sesión actual.
    """

    def __init__(self, directorio_salida: str, video_path: str) -> None:
        self._ruta_estado = Path(directorio_salida) / CHECKPOINT_FILENAME
        self._video_path = str(Path(video_path).resolve()) if video_path else ""
        self._estado: Optional[dict] = None
        self._contador_segmentos = 0

    # ------------------------------------------------------------------
    # Propiedades de acceso rápido
    # ------------------------------------------------------------------

    @property
    def ruta_estado(self) -> Path:
        return self._ruta_estado

    @property
    def estado(self) -> dict:
        if self._estado is None:
            self._estado = self._cargar_o_inicializar()
        return self._estado

    @property
    def fase_actual(self) -> str:
        return self.estado["fase_actual"]

    @property
    def ultimo_timestamp(self) -> float:
        return float(self.estado.get("ultimo_timestamp", 0.0))

    @property
    def segmentos_transcritos(self) -> List[str]:
        return self.estado.get("segmentos_transcritos", [])

    # ------------------------------------------------------------------
    # Lógica de carga / inicialización
    # ------------------------------------------------------------------

    def _cargar_o_inicializar(self) -> dict:
        if self._ruta_estado.exists():
            try:
                with open(self._ruta_estado, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                if self._es_estado_valido(datos):
                    return datos
            except (json.JSONDecodeError, OSError):
                pass
        return _estado_inicial(self._video_path)

    @staticmethod
    def _es_estado_valido(datos: dict) -> bool:
        claves_requeridas = {
            "video_path",
            "fase_actual",
            "ultimo_timestamp",
            "segmentos_transcritos",
            "fecha_actualizacion",
        }
        return claves_requeridas.issubset(datos.keys())

    # ------------------------------------------------------------------
    # Escritura a disco (atómica)
    # ------------------------------------------------------------------

    def _persistir(self) -> None:
        self._estado["fecha_actualizacion"] = _ahora_iso()
        ruta_tmp = self._ruta_estado.with_suffix(".tmp")
        try:
            with open(ruta_tmp, "w", encoding="utf-8") as f:
                json.dump(self._estado, f, ensure_ascii=False, indent=2)
            os.replace(ruta_tmp, self._ruta_estado)
        except OSError as exc:
            print(f"[CHECKPOINT] Advertencia: no se pudo persistir el estado: {exc}", flush=True)
            if ruta_tmp.exists():
                try:
                    ruta_tmp.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def existe_sesion_previa(self) -> bool:
        if not self._ruta_estado.exists():
            return False
        try:
            with open(self._ruta_estado, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if not self._es_estado_valido(datos):
                return False
            return datos.get("fase_actual") != FASE_COMPLETADO
        except (json.JSONDecodeError, OSError):
            return False

    def inicializar_nueva_sesion(self) -> None:
        self._estado = _estado_inicial(self._video_path)
        self._contador_segmentos = 0
        self._persistir()

    def registrar_segmento(
        self,
        texto: str,
        timestamp_segundos: float,
        forzar_guardado: bool = False,
    ) -> None:
        _ = self.estado
        self._estado["segmentos_transcritos"].append(texto)
        self._estado["ultimo_timestamp"] = float(timestamp_segundos)
        self._contador_segmentos += 1

        if forzar_guardado or self._contador_segmentos % CHECKPOINT_INTERVAL_SEGMENTOS == 0:
            self._persistir()

    def avanzar_fase(self, fase: str) -> None:
        _ = self.estado
        self._estado["fase_actual"] = fase
        self._persistir()

    def marcar_completado(self) -> None:
        self.avanzar_fase(FASE_COMPLETADO)

    def purgar(self) -> None:
        try:
            if self._ruta_estado.exists():
                self._ruta_estado.unlink()
        except OSError as exc:
            print(f"[CHECKPOINT] Advertencia: no se pudo eliminar el estado: {exc}", flush=True)

    def cargar_estado_existente(self) -> Optional[dict]:
        if not self._ruta_estado.exists():
            return None
        try:
            with open(self._ruta_estado, "r", encoding="utf-8") as f:
                datos = json.load(f)
            return datos if self._es_estado_valido(datos) else None
        except (json.JSONDecodeError, OSError):
            return None


# ---------------------------------------------------------------------------
# Funciones utilitarias de módulo
# ---------------------------------------------------------------------------

def obtener_ruta_checkpoint(directorio_clase: str) -> Path:
    return Path(directorio_clase) / CHECKPOINT_FILENAME


def leer_estado_si_existe(directorio_clase: str) -> Optional[dict]:
    """Lee y valida el estado persistido sin instanciar CheckpointManager.

    Devuelve None si el archivo no existe, está corrupto o ya está completado.
    """
    ruta = obtener_ruta_checkpoint(directorio_clase)
    if not ruta.exists():
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        claves = {
            "video_path", "fase_actual", "ultimo_timestamp",
            "segmentos_transcritos", "fecha_actualizacion",
        }
        if not claves.issubset(datos.keys()):
            return None
        if datos.get("fase_actual") == FASE_COMPLETADO:
            return None
        return datos
    except (json.JSONDecodeError, OSError):
        return None
