"""Servicio de exportación y notificación desacoplado para LectureFlow (Notion y Telegram)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from src.orchestrator import normalizar_nombre, es_ruta_segura
from src.notion_exporter import exportar_apuntes_a_notion, notion_configurado
from src.notificador import notificar_clase_completada, telegram_configurado

logger = logging.getLogger("export_service")
ROOT_DIR_DEFECTO = Path(__file__).resolve().parent.parent.parent


def exportar_clase_a_notion(
    root_dir: Optional[Path],
    materia: str,
    clase: str,
) -> Dict[str, Any]:
    """Exporta los apuntes Markdown de una clase a la base de datos de Notion."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    # Verificación preventiva contra Path Traversal
    ruta_tentativa = carpeta_clases / materia / clase
    if not es_ruta_segura(ruta_tentativa, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

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
        raise FileNotFoundError(f"No existen apuntes.md para la clase '{slug_clase}'. Genera los apuntes primero.")

    contenido = ruta_apuntes.read_text(encoding="utf-8").strip()
    if not contenido:
        raise ValueError("El archivo 'apuntes.md' está vacío. No hay contenido para exportar.")

    if not notion_configurado():
        raise ValueError("Faltan NOTION_TOKEN y/o NOTION_DATABASE_ID en el entorno o archivo .env.")

    # Formatear títulos legibles
    titulo_formateado = slug_clase.replace("_", " ")
    materia_formateada = slug_materia.replace("_", " ")

    try:
        url_notion = exportar_apuntes_a_notion(
            titulo_clase=titulo_formateado,
            materia=materia_formateada,
            markdown_texto=contenido,
        )
    except ValueError as e:
        raise ValueError(f"Configuración inválida de Notion: {e}")
    except Exception as e:
        logger.error("[EXPORT NOTION] Error exportando clase %s a Notion: %s", slug_clase, e)
        raise RuntimeError(f"Error de comunicación con la API de Notion: {e}")

    return {
        "status": "ok",
        "url_notion": url_notion,
        "mensaje": "Exportado con éxito a Notion",
    }


def notificar_clase_por_telegram(
    root_dir: Optional[Path],
    materia: str,
    clase: str,
    url_notion: Optional[str] = None,
) -> Dict[str, Any]:
    """Envía una notificación a Telegram sobre la clase con enlace opcional a Notion."""
    base = Path(root_dir) if root_dir is not None else ROOT_DIR_DEFECTO
    carpeta_clases = base / "clases"

    # Verificación preventiva contra Path Traversal
    ruta_tentativa = carpeta_clases / materia / clase
    if not es_ruta_segura(ruta_tentativa, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    slug_materia = normalizar_nombre(materia.strip())
    slug_clase = normalizar_nombre(clase.strip())

    if not slug_materia or not slug_clase:
        raise ValueError("Identificadores de materia o clase no válidos.")

    ruta_clase = carpeta_clases / slug_materia / slug_clase
    if not es_ruta_segura(ruta_clase, carpeta_clases):
        raise ValueError("Violación de seguridad de rutas (Path Traversal detectado).")

    if not ruta_clase.exists() or not ruta_clase.is_dir():
        raise FileNotFoundError(f"La clase '{slug_clase}' no existe en la materia '{slug_materia}'.")

    if not telegram_configurado():
        raise ValueError("Variables TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID no configuradas en el entorno o .env.")

    titulo_formateado = slug_clase.replace("_", " ")
    enviado = notificar_clase_completada(
        nombre_clase=titulo_formateado,
        duracion="Exportación manual",
        url_notion=url_notion,
    )

    if not enviado:
        raise RuntimeError("Fallo al enviar notificación por Telegram. Revisa el token, chat ID o conexión.")

    return {
        "status": "ok",
        "mensaje": "Notificación enviada a Telegram",
    }
