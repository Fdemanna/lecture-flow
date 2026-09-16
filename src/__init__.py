"""Paquete modular de procesamiento y servicios de LectureFlow."""

from src.procesar_clase import normalizar_nombre, ejecutar_pipeline
from src.notion_exporter import exportar_a_notion
from src.transcribir import transcribir_archivo
from src.generar_apuntes import generar_material_estudio

__all__ = [
    "normalizar_nombre",
    "ejecutar_pipeline",
    "exportar_a_notion",
    "transcribir_archivo",
    "generar_material_estudio",
]
