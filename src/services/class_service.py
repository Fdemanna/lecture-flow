"""Servicio de lectura y gestión para el árbol de asignaturas y clases de LectureFlow."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.orchestrator import normalizar_nombre, es_ruta_segura

ROOT_DIR_DEFECTO = Path(__file__).resolve().parent.parent.parent


def obtener_arbol_clases(root_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Escanea el directorio 'clases/' y devuelve la jerarquía de materias y temas.

    Parámetros
    ----------
    root_dir:
        Ruta raíz del proyecto. Si no se especifica, se utiliza el directorio raíz
        por defecto del repositorio.

    Devuelve
    --------
    List[Dict[str, Any]]
        Lista de materias ordenadas alfabéticamente con la información de sus clases
        y el estado de los artefactos generados (apuntes.md, preguntas.json).
    """
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    if not carpeta_clases.exists() or not carpeta_clases.is_dir():
        return []

    arbol: List[Dict[str, Any]] = []

    directorios_materias = sorted([
        d for d in carpeta_clases.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ], key=lambda x: x.name.lower())

    for d_materia in directorios_materias:
        nombre_materia = d_materia.name
        nombre_materia_legible = nombre_materia.replace("_", " ")

        directorios_clases = sorted([
            c for c in d_materia.iterdir()
            if c.is_dir() and not c.name.startswith(".")
        ], key=lambda x: x.name.lower())

        lista_clases: List[Dict[str, Any]] = []
        for d_clase in directorios_clases:
            nombre_clase = d_clase.name
            nombre_clase_legible = nombre_clase.replace("_", " ")

            tiene_apuntes = (d_clase / "apuntes.md").is_file()
            tiene_preguntas = (d_clase / "preguntas.json").is_file()
            tiene_transcripcion = (
                (d_clase / "transcripcion.json").is_file() or
                (d_clase / "transcripcion.txt").is_file()
            )

            lista_clases.append({
                "id": nombre_clase,
                "nombre": nombre_clase_legible,
                "tiene_apuntes": tiene_apuntes,
                "tiene_preguntas": tiene_preguntas,
                "tiene_transcripcion": tiene_transcripcion,
                "ruta_relativa": f"clases/{nombre_materia}/{nombre_clase}",
            })

        arbol.append({
            "materia": nombre_materia,
            "materia_nombre": nombre_materia_legible,
            "total_clases": len(lista_clases),
            "clases": lista_clases,
        })

    return arbol


def renombrar_materia(
    root_dir: Optional[Path],
    nombre_actual: str,
    nuevo_nombre: str,
) -> Dict[str, Any]:
    """Renombra una carpeta de asignatura existente dentro de 'clases/'.

    Valida la seguridad de la ruta y normaliza el identificador para prevenir
    ataques de Path Traversal o caracteres problemáticos.
    """
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    slug_actual = normalizar_nombre(nombre_actual.strip())
    slug_nuevo = normalizar_nombre(nuevo_nombre.strip())

    if not slug_actual or not slug_nuevo:
        raise ValueError("Los nombres de materia no pueden estar vacíos ni contener sólo caracteres inválidos.")

    ruta_origen = carpeta_clases / slug_actual
    ruta_destino = carpeta_clases / slug_nuevo

    if not es_ruta_segura(ruta_origen, carpeta_clases) or not es_ruta_segura(ruta_destino, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    if not ruta_origen.exists() or not ruta_origen.is_dir():
        raise FileNotFoundError(f"La materia '{slug_actual}' no existe en el sistema.")

    if ruta_destino.exists() and ruta_destino.resolve() != ruta_origen.resolve():
        raise FileExistsError(f"Ya existe una asignatura con el nombre '{slug_nuevo}'.")

    if ruta_destino.resolve() != ruta_origen.resolve():
        ruta_origen.rename(ruta_destino)

    return {
        "status": "ok",
        "materia_anterior": slug_actual,
        "materia_nueva": slug_nuevo,
        "materia_nombre": slug_nuevo.replace("_", " "),
        "mensaje": f"Asignatura renombrada con éxito a '{slug_nuevo}'.",
    }


def eliminar_materia(
    root_dir: Optional[Path],
    nombre_materia: str,
) -> Dict[str, Any]:
    """Elimina permanentemente una asignatura y todas sus clases en 'clases/'."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    slug_materia = normalizar_nombre(nombre_materia.strip())
    if not slug_materia:
        raise ValueError("Nombre de materia no válido.")

    ruta_materia = carpeta_clases / slug_materia

    if not es_ruta_segura(ruta_materia, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    if not ruta_materia.exists() or not ruta_materia.is_dir():
        raise FileNotFoundError(f"La materia '{slug_materia}' no existe.")

    shutil.rmtree(ruta_materia)

    return {
        "status": "ok",
        "materia_eliminada": slug_materia,
        "mensaje": f"Asignatura '{slug_materia}' eliminada correctamente.",
    }


def leer_apuntes_clase(
    root_dir: Optional[Path],
    materia: str,
    clase: str,
) -> Dict[str, Any]:
    """Lee el archivo 'apuntes.md' de una clase específica de forma segura."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    slug_materia = normalizar_nombre(materia.strip())
    slug_clase = normalizar_nombre(clase.strip())

    if not slug_materia or not slug_clase:
        raise ValueError("Identificadores de materia o clase no válidos.")

    ruta_clase = carpeta_clases / slug_materia / slug_clase
    ruta_apuntes = ruta_clase / "apuntes.md"

    if not es_ruta_segura(ruta_apuntes, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    if not ruta_clase.exists() or not ruta_clase.is_dir():
        raise FileNotFoundError(f"La clase '{slug_clase}' no existe en la materia '{slug_materia}'.")

    if not ruta_apuntes.exists():
        return {
            "contenido": "",
            "existe": False,
            "ultima_modificacion": None,
        }

    stat = ruta_apuntes.stat()
    import datetime
    ultima_modificacion = datetime.datetime.fromtimestamp(
        stat.st_mtime, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    contenido = ruta_apuntes.read_text(encoding="utf-8")
    return {
        "contenido": contenido,
        "existe": True,
        "ultima_modificacion": ultima_modificacion,
    }


def guardar_apuntes_clase(
    root_dir: Optional[Path],
    materia: str,
    clase: str,
    contenido: str,
) -> Dict[str, Any]:
    """Guarda 'apuntes.md' de forma atómica usando un archivo temporal y reemplazo."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    slug_materia = normalizar_nombre(materia.strip())
    slug_clase = normalizar_nombre(clase.strip())

    if not slug_materia or not slug_clase:
        raise ValueError("Identificadores de materia o clase no válidos.")

    ruta_clase = carpeta_clases / slug_materia / slug_clase
    ruta_apuntes = ruta_clase / "apuntes.md"

    if not es_ruta_segura(ruta_apuntes, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    if not ruta_clase.exists() or not ruta_clase.is_dir():
        raise FileNotFoundError(f"La clase '{slug_clase}' no existe en la materia '{slug_materia}'.")

    ruta_tmp = ruta_clase / ".apuntes.md.tmp"
    try:
        ruta_tmp.write_text(contenido, encoding="utf-8")
        ruta_tmp.replace(ruta_apuntes)
    finally:
        if ruta_tmp.exists():
            ruta_tmp.unlink(missing_ok=True)

    stat = ruta_apuntes.stat()
    import datetime
    ultima_modificacion = datetime.datetime.fromtimestamp(
        stat.st_mtime, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    return {
        "status": "ok",
        "mensaje": "Apuntes actualizados correctamente",
        "ultima_modificacion": ultima_modificacion,
    }
