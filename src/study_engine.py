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


# ==============================================================================
# ESTADÍSTICAS Y GESTIÓN DE SESIÓN DE ESTUDIO (Active Recall)
# ==============================================================================

def obtener_estadisticas_estudio(ruta_archivo: Optional[Path] = None) -> Dict[str, Any]:
    """Obtiene y resume el progreso de estudio del usuario (SM-2 Lite)."""
    progreso = obtener_progreso(ruta_archivo)

    historial = progreso.get("historial_preguntas", {})
    if not isinstance(historial, dict):
        historial = {}

    total_preguntas = len(historial)
    preguntas_dominadas = sum(
        1 for p in historial.values()
        if isinstance(p, dict) and p.get("intervalo_dias", p.get("intervalo", 0)) >= 7
    )

    return {
        "racha_actual": progreso.get("racha_actual", 0),
        "ultimo_dia_estudiado": progreso.get("ultimo_dia_estudiado"),
        "xp_total": progreso.get("xp_total", 0),
        "total_preguntas_registradas": total_preguntas,
        "preguntas_dominadas": preguntas_dominadas,
        "historial_preguntas": historial,
    }


def obtener_preguntas_sesion(
    root_dir: Optional[Path] = None,
    limite: int = 5,
) -> List[Dict[str, Any]]:
    """Obtiene lote de preguntas prioritarias sanitizadas (sin respuestas ni explicaciones)."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR
    preguntas_raw = obtener_preguntas_disponibles(root_dir=base, limite=limite)

    resultado: List[Dict[str, Any]] = []
    for p in preguntas_raw:
        resultado.append({
            "id": p["id"],
            "materia": p.get("materia", ""),
            "materia_nombre": p.get("materia", "").replace("_", " "),
            "clase": p.get("clase", ""),
            "clase_nombre": p.get("clase", "").replace("_", " "),
            "tipo": p.get("tipo", "conceptual"),
            "pregunta": p.get("pregunta", ""),
            "codigo": p.get("codigo", ""),
            "opciones": p.get("opciones", []),
        })
    return resultado


def verificar_y_registrar_respuesta(
    question_id: str,
    selected_option: int,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Valida la opción seleccionada, aplica el algoritmo SM-2 y actualiza la racha."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR
    carpeta_clases = base / "clases"

    pregunta_encontrada: Optional[Dict[str, Any]] = None
    if carpeta_clases.exists():
        for ruta_json in carpeta_clases.glob("**/preguntas.json"):
            try:
                with open(ruta_json, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    if isinstance(datos, list):
                        for item in datos:
                            if isinstance(item, dict) and item.get("id") == question_id:
                                pregunta_encontrada = item
                                break
            except Exception:
                continue
            if pregunta_encontrada:
                break

    if not pregunta_encontrada:
        raise FileNotFoundError(f"No se encontró la pregunta con ID '{question_id}'.")

    correcta_idx = int(pregunta_encontrada.get("correcta", pregunta_encontrada.get("respuesta_correcta", 0)))
    es_correcta = int(selected_option) == correcta_idx
    explicacion = pregunta_encontrada.get("explicacion", "Sin explicación pedagógica disponible.")

    # 1. Registrar en SM-2 Lite
    registrar_respuesta(id_pregunta=question_id, acierto=es_correcta)

    # 2. Actualizar racha diaria si es correcta
    if es_correcta:
        actualizar_racha()

    progreso_actualizado = obtener_progreso()

    return {
        "correct": es_correcta,
        "correct_index": correcta_idx,
        "explanation": explicacion,
        "question_id": question_id,
        "stats": progreso_actualizado,
    }
