"""Módulo de compatibilidad para el servicio de estudio.

DEPRECATION NOTE:
Las funciones de Active Recall y repetición espaciada residen directamente
en 'src.study_engine' para consolidar la lógica de dominio en un único módulo profundo.
Por favor, importa directamente:
    from src.study_engine import (
        obtener_estadisticas_estudio,
        obtener_preguntas_sesion,
        verificar_y_registrar_respuesta,
    )
"""
from __future__ import annotations

from src.study_engine import (
    obtener_estadisticas_estudio,
    obtener_preguntas_sesion,
    verificar_y_registrar_respuesta,
)

__all__ = [
    "obtener_estadisticas_estudio",
    "obtener_preguntas_sesion",
    "verificar_y_registrar_respuesta",
]
