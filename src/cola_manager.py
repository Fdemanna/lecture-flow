"""
Módulo de gestión de cola de procesamiento por lotes para LectureFlow.

Persiste el estado de todos los trabajos pendientes/en curso/completados en
un archivo ``cola_trabajo.json`` ubicado en la raíz del proyecto (ROOT_DIR).

Esquema del archivo de cola
-----------------------------
{
  "trabajos": [
    {
      "id": "<sha256_corto>",
      "video_path": "ruta/absoluta/al/archivo",
      "materia": "Programacion",
      "nombre_clase": "Tema_1_Algoritmos",
      "directorio_clase": "ruta/absoluta/a/clases/Programacion/Tema_1",
      "estado": "pendiente | en_progreso | completado | error",
      "error_msg": null,
      "creado_en": "ISO-8601",
      "completado_en": null
    }
  ]
}
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
COLA_FILENAME = "cola_trabajo.json"

ESTADO_PENDIENTE = "pendiente"
ESTADO_EN_PROGRESO = "en_progreso"
ESTADO_COMPLETADO = "completado"
ESTADO_ERROR = "error"

_CLAVES_TRABAJO = {
    "id", "video_path", "materia", "nombre_clase",
    "directorio_clase", "estado", "error_msg", "creado_en", "completado_en",
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id_trabajo(video_path: str, nombre_clase: str) -> str:
    """Genera un identificador corto reproducible a partir del path y la clase."""
    raw = f"{Path(video_path).resolve()}::{nombre_clase}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _trabajo_nuevo(
    video_path: str,
    materia: str,
    nombre_clase: str,
    directorio_clase: str,
) -> dict:
    return {
        "id": _id_trabajo(video_path, nombre_clase),
        "video_path": str(Path(video_path).resolve()),
        "materia": materia,
        "nombre_clase": nombre_clase,
        "directorio_clase": str(Path(directorio_clase).resolve()),
        "estado": ESTADO_PENDIENTE,
        "error_msg": None,
        "creado_en": _ahora_iso(),
        "completado_en": None,
    }


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class ColaManager:
    """Gestiona la cola de trabajos de procesamiento por lotes.

    Parámetros
    ----------
    ruta_cola:
        Ruta absoluta al archivo ``cola_trabajo.json``.
        Normalmente la raíz del proyecto.
    """

    def __init__(self, ruta_cola: str, reconciliar_al_iniciar: bool = False) -> None:
        self._ruta = Path(ruta_cola)
        if reconciliar_al_iniciar:
            self.reconciliar_trabajos_huerfanos()

    # ------------------------------------------------------------------
    # I/O atómica
    # ------------------------------------------------------------------

    def _leer(self) -> dict:
        if self._ruta.exists():
            try:
                with open(self._ruta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                if isinstance(datos, dict) and "trabajos" in datos:
                    return datos
            except (json.JSONDecodeError, OSError):
                pass
        return {"trabajos": []}

    def _escribir(self, datos: dict) -> None:
        tmp = self._ruta.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._ruta)
        except OSError as exc:
            print(f"[COLA] Advertencia: no se pudo persistir la cola: {exc}", flush=True)
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def agregar_trabajos(
        self,
        entradas: List[dict],
    ) -> List[dict]:
        """Añade una lista de trabajos nuevos a la cola.

        Parámetros
        ----------
        entradas:
            Lista de dicts con claves ``video_path``, ``materia``,
            ``nombre_clase`` y ``directorio_clase``.

        Devuelve la lista de trabajos efectivamente añadidos (omite duplicados
        por ``id``).
        """
        datos = self._leer()
        ids_existentes = {t["id"] for t in datos["trabajos"]}
        agregados = []
        for entrada in entradas:
            trabajo = _trabajo_nuevo(
                entrada["video_path"],
                entrada["materia"],
                entrada["nombre_clase"],
                entrada["directorio_clase"],
            )
            if trabajo["id"] not in ids_existentes:
                datos["trabajos"].append(trabajo)
                ids_existentes.add(trabajo["id"])
                agregados.append(trabajo)
        self._escribir(datos)
        return agregados

    def listar_trabajos(self) -> List[dict]:
        """Devuelve la lista completa de trabajos tal como está en disco."""
        return self._leer()["trabajos"]

    def obtener_siguiente_pendiente(self) -> Optional[dict]:
        """Devuelve el primer trabajo en estado 'pendiente', o None si no hay."""
        for t in self._leer()["trabajos"]:
            if t.get("estado") == ESTADO_PENDIENTE:
                return t
        return None

    def actualizar_estado(
        self,
        trabajo_id: str,
        estado: str,
        error_msg: Optional[str] = None,
    ) -> None:
        """Actualiza el estado de un trabajo identificado por su ``id``.

        Parámetros
        ----------
        trabajo_id:
            Identificador del trabajo.
        estado:
            Nuevo estado. Una de las constantes ``ESTADO_*`` del módulo.
        error_msg:
            Mensaje de error opcional (solo para estado ``error``).
        """
        datos = self._leer()
        for t in datos["trabajos"]:
            if t["id"] == trabajo_id:
                t["estado"] = estado
                if error_msg is not None:
                    t["error_msg"] = error_msg
                if estado == ESTADO_COMPLETADO:
                    t["completado_en"] = _ahora_iso()
                    t["error_msg"] = None
                break
        self._escribir(datos)

    def marcar_en_progreso(self, trabajo_id: str) -> None:
        self.actualizar_estado(trabajo_id, ESTADO_EN_PROGRESO)

    def marcar_completado(self, trabajo_id: str) -> None:
        self.actualizar_estado(trabajo_id, ESTADO_COMPLETADO)

    def marcar_error(self, trabajo_id: str, msg: str) -> None:
        self.actualizar_estado(trabajo_id, ESTADO_ERROR, error_msg=msg)

    def reintentar_errores(self) -> int:
        """Vuelve a marcar como 'pendiente' los trabajos en estado 'error'.

        Devuelve el número de trabajos revertidos.
        """
        datos = self._leer()
        n = 0
        for t in datos["trabajos"]:
            if t.get("estado") == ESTADO_ERROR:
                t["estado"] = ESTADO_PENDIENTE
                t["error_msg"] = None
                t["completado_en"] = None
                n += 1
        self._escribir(datos)
        return n

    def reconciliar_trabajos_huerfanos(self) -> int:
        """Busca cualquier trabajo que haya quedado en estado 'en_progreso'
        (debido a caída de sesión de Streamlit, crash o reinicio)
        y lo devuelve a estado 'pendiente' reseteando su error_msg.

        Evita que trabajos interrumpidos queden en deadlock permanente.
        Devuelve el número de trabajos reconciliados.
        """
        datos = self._leer()
        reconciliados = 0
        for t in datos["trabajos"]:
            if t.get("estado") == ESTADO_EN_PROGRESO:
                t["estado"] = ESTADO_PENDIENTE
                t["error_msg"] = None
                reconciliados += 1
        if reconciliados > 0:
            self._escribir(datos)
            print(f"[COLA] {reconciliados} trabajo(s) huérfano(s) en progreso reconciliado(s) a 'pendiente'.", flush=True)
        return reconciliados

    def limpiar_completados(self) -> int:
        """Elimina de la cola todos los trabajos en estado 'completado'.

        Devuelve el número de trabajos eliminados.
        """
        datos = self._leer()
        antes = len(datos["trabajos"])
        datos["trabajos"] = [
            t for t in datos["trabajos"]
            if t.get("estado") != ESTADO_COMPLETADO
        ]
        eliminados = antes - len(datos["trabajos"])
        self._escribir(datos)
        return eliminados

    def hay_pendientes(self) -> bool:
        return any(
            t.get("estado") in (ESTADO_PENDIENTE, ESTADO_EN_PROGRESO)
            for t in self._leer()["trabajos"]
        )

    def conteo_por_estado(self) -> dict:
        conteo = {
            ESTADO_PENDIENTE: 0,
            ESTADO_EN_PROGRESO: 0,
            ESTADO_COMPLETADO: 0,
            ESTADO_ERROR: 0,
        }
        for t in self._leer()["trabajos"]:
            estado = t.get("estado", ESTADO_PENDIENTE)
            if estado in conteo:
                conteo[estado] += 1
        return conteo

    def purgar_cola(self) -> None:
        """Elimina completamente el archivo de cola del disco."""
        try:
            if self._ruta.exists():
                self._ruta.unlink()
        except OSError as exc:
            print(f"[COLA] No se pudo eliminar el archivo de cola: {exc}", flush=True)


# ---------------------------------------------------------------------------
# Helper de módulo
# ---------------------------------------------------------------------------

def obtener_ruta_cola(root_dir: str) -> Path:
    """Devuelve la ruta estándar al archivo de cola dado el directorio raíz."""
    return Path(root_dir) / COLA_FILENAME
