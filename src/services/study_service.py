"""Servicio de lectura y mutación para Active Recall (SM-2 Lite) en LectureFlow."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.study_engine import (
    obtener_progreso,
    registrar_respuesta,
    actualizar_racha,
    obtener_preguntas_disponibles,
)

ROOT_DIR_DEFECTO = Path(__file__).resolve().parent.parent.parent


def obtener_estadisticas_estudio(ruta_archivo: Optional[Path] = None) -> Dict[str, Any]:
    """Obtiene y resume el progreso de estudio del usuario (SM-2 Lite)."""
    progreso = obtener_progreso(ruta_archivo)

    historial = progreso.get("historial_preguntas", {})
    if not isinstance(historial, dict):
        historial = {}

    total_preguntas = len(historial)
    preguntas_dominadas = sum(
        1 for p in historial.values()
        if isinstance(p, dict) and p.get("intervalo_dias", 0) >= 7
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
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
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
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
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
