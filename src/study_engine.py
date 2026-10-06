"""Motor de Repetición Espaciada (SM-2 Lite), cálculo de racha y gestión de progreso de estudio."""
from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from pathlib import Path
import random
from typing import Optional, Dict, Any, List

logger = logging.getLogger("study_engine")

ROOT_DIR = Path(__file__).resolve().parent.parent
RUTA_PROGRESO_DEFECTO = ROOT_DIR / "data" / "progreso_estudio.json"

ESTRUCTURA_BASE_PROGRESO: Dict[str, Any] = {
    "racha_actual": 0,
    "ultimo_dia_estudiado": None,
    "xp_total": 0,
    "historial_preguntas": {},
}


def _resolver_ruta_progreso(ruta_archivo: Optional[Path] = None) -> Path:
    """Devuelve la ruta canónica al archivo de progreso."""
    if ruta_archivo is not None:
        return Path(ruta_archivo)
    return RUTA_PROGRESO_DEFECTO


def obtener_progreso(ruta_archivo: Optional[Path] = None) -> dict:
    """Lee el archivo JSON de progreso de forma segura y devuelve su contenido.

    Si el archivo o directorio no existe o el JSON está corrupto, se inicializa
    con la estructura base por defecto.
    """
    ruta = _resolver_ruta_progreso(ruta_archivo)
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        guardar_progreso(ESTRUCTURA_BASE_PROGRESO, ruta)
        return dict(ESTRUCTURA_BASE_PROGRESO)

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
            if not isinstance(datos, dict):
                datos = dict(ESTRUCTURA_BASE_PROGRESO)
    except Exception as exc:
        logger.warning("Fallo al leer '%s': %s. Restaurando estructura base.", ruta, exc)
        datos = dict(ESTRUCTURA_BASE_PROGRESO)

    # Garantizar presencia de todas las claves requeridas
    for clave, valor_defecto in ESTRUCTURA_BASE_PROGRESO.items():
        if clave not in datos:
            datos[clave] = valor_defecto

    if not isinstance(datos.get("historial_preguntas"), dict):
        datos["historial_preguntas"] = {}

    return datos


def guardar_progreso(datos: dict, ruta_archivo: Optional[Path] = None) -> None:
    """Escribe en el archivo JSON con ensure_ascii=False e indent=2."""
    ruta = _resolver_ruta_progreso(ruta_archivo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temp_ruta = ruta.with_suffix(".tmp")
    try:
        with open(temp_ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        temp_ruta.replace(ruta)
    except Exception as exc:
        logger.error("Error al persistir el progreso de estudio en '%s': %s", ruta, exc)
        if temp_ruta.exists():
            try:
                temp_ruta.unlink()
            except OSError:
                pass
        raise


def actualizar_racha(ruta_archivo: Optional[Path] = None) -> int:
    """Actualiza la racha diaria del estudiante según la fecha de último estudio.

    - Si es igual a hoy: mantiene la racha.
    - Si es igual a ayer: racha_actual += 1.
    - Si es anterior a ayer o null: racha_actual = 1.
    Guarda ultimo_dia_estudiado con la fecha de hoy (YYYY-MM-DD) y persiste los cambios.
    """
    progreso = obtener_progreso(ruta_archivo)
    hoy = date.today()
    hoy_str = hoy.isoformat()
    ayer_str = (hoy - timedelta(days=1)).isoformat()
    ultimo = progreso.get("ultimo_dia_estudiado")
    racha_actual = int(progreso.get("racha_actual", 0))

    if ultimo == hoy_str:
        # Ya estudió hoy: mantener racha existente (o al menos 1)
        racha_actual = max(1, racha_actual)
    elif ultimo == ayer_str:
        # Estudió ayer consecutivamente: incrementar racha
        racha_actual += 1
    else:
        # Primer estudio o racha rota: reiniciar a 1
        racha_actual = 1

    progreso["racha_actual"] = racha_actual
    progreso["ultimo_dia_estudiado"] = hoy_str
    guardar_progreso(progreso, ruta_archivo)
    return racha_actual


def registrar_respuesta(
    id_pregunta: str,
    acierto: bool,
    xp_ganado: int = 10,
    ruta_archivo: Optional[Path] = None,
) -> dict:
    """Implementa el algoritmo SM-2 Lite en historial_preguntas[id_pregunta].

    - Si es acierto:
        * repeticiones += 1
        * intervalo = 1 si repeticiones == 1; 3 si repeticiones == 2; round(intervalo * 2.5) en adelante.
        * suma xp_ganado a xp_total.
    - Si es fallo:
        * repeticiones = 0
        * intervalo = 1
    Calcula proximo_repaso = hoy + timedelta(days=intervalo) y persiste los cambios.
    """
    progreso = obtener_progreso(ruta_archivo)
    historial = progreso.setdefault("historial_preguntas", {})
    registro = historial.get(id_pregunta, {
        "repeticiones": 0,
        "intervalo": 1,
        "aciertos": 0,
        "fallos": 0,
        "ultimo_repaso": None,
        "proximo_repaso": None,
    })

    repeticiones = int(registro.get("repeticiones", 0))
    intervalo = int(registro.get("intervalo", 1))

    if acierto:
        repeticiones += 1
        if repeticiones == 1:
            intervalo = 1
        elif repeticiones == 2:
            intervalo = 3
        else:
            intervalo = max(1, round(intervalo * 2.5))

        registro["repeticiones"] = repeticiones
        registro["intervalo"] = intervalo
        registro["aciertos"] = int(registro.get("aciertos", 0)) + 1
        progreso["xp_total"] = int(progreso.get("xp_total", 0)) + max(0, xp_ganado)
    else:
        registro["repeticiones"] = 0
        registro["intervalo"] = 1
        registro["fallos"] = int(registro.get("fallos", 0)) + 1

    hoy = date.today()
    registro["ultimo_repaso"] = hoy.isoformat()
    registro["proximo_repaso"] = (hoy + timedelta(days=intervalo)).isoformat()

    historial[id_pregunta] = registro
    guardar_progreso(progreso, ruta_archivo)
    return {
        "id_pregunta": id_pregunta,
        "acierto": acierto,
        "registro": registro,
        "racha_actual": progreso.get("racha_actual", 0),
        "xp_total": progreso.get("xp_total", 0),
    }


def obtener_preguntas_disponibles(
    root_dir: Path,
    materia: Optional[str] = None,
    limite: int = 5,
    ruta_archivo_progreso: Optional[Path] = None,
) -> list[dict]:
    """Escanea carpetas en 'clases/' buscando archivos 'preguntas.json'.

    Prioriza preguntas cuya fecha 'proximo_repaso' sea menor o igual a hoy,
    o que nunca hayan sido respondidas. Rellena con preguntas aleatorias
    hasta alcanzar el límite especificado.
    """
    carpeta_base = Path(root_dir) / "clases"
    if not carpeta_base.exists():
        return []

    candidatos_archivos: List[Path] = []
    if materia:
        dir_materia = carpeta_base / materia
        if dir_materia.exists():
            candidatos_archivos = list(dir_materia.glob("**/preguntas.json"))
    else:
        candidatos_archivos = list(carpeta_base.glob("**/preguntas.json"))

    todas_preguntas: List[dict] = []
    vistos_ids = set()

    for ruta_json in candidatos_archivos:
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                datos = json.load(f)
                if isinstance(datos, list):
                    for item in datos:
                        if isinstance(item, dict) and "id" in item:
                            pid = item["id"]
                            if pid not in vistos_ids:
                                vistos_ids.add(pid)
                                todas_preguntas.append(item)
        except Exception as exc:
            logger.warning("No se pudo leer el archivo de preguntas '%s': %s", ruta_json, exc)

    if not todas_preguntas:
        return []

    progreso = obtener_progreso(ruta_archivo_progreso)
    historial = progreso.get("historial_preguntas", {})
    hoy_str = date.today().isoformat()

    prioritarias: List[dict] = []
    secundarias: List[dict] = []

    for p in todas_preguntas:
        pid = p["id"]
        registro = historial.get(pid)
        if registro is None:
            # Nunca respondida -> Prioridad alta
            prioritarias.append(p)
        else:
            proximo = registro.get("proximo_repaso")
            if not proximo or proximo <= hoy_str:
                # Vencida o para repasar hoy -> Prioridad alta
                prioritarias.append(p)
            else:
                # Ya repasada y al día -> Secundaria
                secundarias.append(p)

    random.shuffle(prioritarias)
    random.shuffle(secundarias)

    seleccionadas = prioritarias[:limite]
    if len(seleccionadas) < limite:
        restantes = limite - len(seleccionadas)
        seleccionadas.extend(secundarias[:restantes])

    return seleccionadas
