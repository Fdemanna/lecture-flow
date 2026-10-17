"""Tests unitarios para el motor de estudio profundizado en src/study_engine.py."""
import json
from pathlib import Path
import pytest

from src.study_engine import (
    obtener_progreso,
    guardar_progreso,
    actualizar_racha,
    registrar_respuesta,
    obtener_estadisticas_estudio,
    obtener_preguntas_sesion,
    verificar_y_registrar_respuesta,
)


@pytest.fixture
def entorno_estudio(tmp_path):
    """Crea una estructura de directorios y progreso sintético para pruebas."""
    ruta_progreso = tmp_path / "data" / "progreso_estudio.json"
    carpeta_clases = tmp_path / "clases" / "Sistemas" / "Tema_01"
    carpeta_clases.mkdir(parents=True, exist_ok=True)

    preguntas_fixture = [
        {
            "id": "q_001",
            "materia": "Sistemas",
            "clase": "Tema_01",
            "tipo": "conceptual",
            "pregunta": "¿Qué componente gestiona la memoria virtual?",
            "codigo": "",
            "opciones": ["MMU", "ALU", "BIOS", "DMA"],
            "correcta": 0,
            "explicacion": "La MMU (Memory Management Unit) traduce direcciones virtuales a físicas.",
        },
        {
            "id": "q_002",
            "materia": "Sistemas",
            "clase": "Tema_01",
            "tipo": "codigo",
            "pregunta": "¿Qué código compila sin errores?",
            "codigo": "int main() { return 0; }",
            "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"],
            "correcta": 1,
            "explicacion": "La opción B es la sintácticamente correcta.",
        },
    ]

    with open(carpeta_clases / "preguntas.json", "w", encoding="utf-8") as f:
        json.dump(preguntas_fixture, f, ensure_ascii=False, indent=2)

    return {
        "root_dir": tmp_path,
        "ruta_progreso": ruta_progreso,
        "preguntas": preguntas_fixture,
    }


def test_obtener_estadisticas_estudio_vacio(tmp_path):
    """Comprueba las estadísticas iniciales cuando no hay historial."""
    ruta_progreso = tmp_path / "data" / "progreso_vacio.json"
    stats = obtener_estadisticas_estudio(ruta_progreso)

    assert stats["racha_actual"] == 0
    assert stats["xp_total"] == 0
    assert stats["total_preguntas_registradas"] == 0
    assert stats["preguntas_dominadas"] == 0
    assert stats["historial_preguntas"] == {}


def test_obtener_estadisticas_estudio_con_preguntas_dominadas(tmp_path):
    """Comprueba el cómputo de preguntas dominadas con intervalo >= 7 días."""
    ruta_progreso = tmp_path / "data" / "progreso.json"
    datos = {
        "racha_actual": 3,
        "ultimo_dia_estudiado": "2026-10-17",
        "xp_total": 150,
        "historial_preguntas": {
            "q_001": {"intervalo": 1, "aciertos": 1, "fallos": 0},
            "q_002": {"intervalo": 7, "aciertos": 3, "fallos": 0},
            "q_003": {"intervalo": 18, "aciertos": 4, "fallos": 0},
        },
    }
    guardar_progreso(datos, ruta_progreso)

    stats = obtener_estadisticas_estudio(ruta_progreso)
    assert stats["racha_actual"] == 3
    assert stats["xp_total"] == 150
    assert stats["total_preguntas_registradas"] == 3
    assert stats["preguntas_dominadas"] == 2


def test_obtener_preguntas_sesion_sanitizadas(entorno_estudio):
    """Verifica que las preguntas para la sesión no filtran la respuesta correcta ni la explicación."""
    root_dir = entorno_estudio["root_dir"]
    lote = obtener_preguntas_sesion(root_dir=root_dir, limite=5)

    assert len(lote) == 2
    for item in lote:
        assert "id" in item
        assert "pregunta" in item
        assert "opciones" in item
        assert "materia_nombre" in item
        assert "clase_nombre" in item
        # Invariante de seguridad: nunca enviar respuestas ni explicaciones en el lote inicial
        assert "correcta" not in item
        assert "respuesta_correcta" not in item
        assert "explicacion" not in item


def test_verificar_y_registrar_respuesta_acierto(entorno_estudio):
    """Verifica el flujo de respuesta correcta con avance de SM-2."""
    root_dir = entorno_estudio["root_dir"]
    resultado = verificar_y_registrar_respuesta(
        question_id="q_001",
        selected_option=0,
        root_dir=root_dir,
    )

    assert resultado["correct"] is True
    assert resultado["correct_index"] == 0
    assert "MMU" in resultado["explanation"]
    assert resultado["question_id"] == "q_001"
    assert resultado["stats"]["racha_actual"] >= 1
    assert resultado["stats"]["xp_total"] >= 10


def test_verificar_y_registrar_respuesta_fallo(entorno_estudio):
    """Verifica el flujo de respuesta incorrecta con reinicio de intervalo en SM-2."""
    root_dir = entorno_estudio["root_dir"]
    resultado = verificar_y_registrar_respuesta(
        question_id="q_001",
        selected_option=2,
        root_dir=root_dir,
    )

    assert resultado["correct"] is False
    assert resultado["correct_index"] == 0
    assert resultado["question_id"] == "q_001"


def test_verificar_pregunta_inexistente(entorno_estudio):
    """Comprueba que lanza FileNotFoundError si el ID de la pregunta no existe."""
    root_dir = entorno_estudio["root_dir"]
    with pytest.raises(FileNotFoundError):
        verificar_y_registrar_respuesta(
            question_id="id_desconocido",
            selected_option=0,
            root_dir=root_dir,
        )
