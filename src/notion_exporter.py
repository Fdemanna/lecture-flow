"""
Módulo de exportación a Notion para Asistente DAW.
Diseño pulido y optimizado para estudio técnico:
- Compatible con Python 3.9+ (uso de typing.Optional y typing.Tuple).
- Índice nativo limpio (ignora encabezados mecánicos de bloques para no saturar).
- Detección inteligente de esquema de base de datos (tolerante a nombres de columnas).
- Toggles automáticos para Glosarios, Secciones por Bloque, Exámenes y Checklists.
- Callouts coloreados según contexto (Azul: Ejemplos, Naranja: Trampas/Avisos, Rojo: Errores).
- División en lotes de 100 bloques (límite API Notion).
"""

import os
from pathlib import Path
import re
import time
import logging
from typing import Optional, Tuple, List
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT_DIR / ".env")
except ImportError:
    pass

logger = logging.getLogger("notion_exporter")


def obtener_credencial(clave: str) -> str:
    valor = os.getenv(clave)
    if not valor:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and clave in st.secrets:
                valor = str(st.secrets[clave])
        except Exception:
            valor = None
    return valor or ""


def notion_configurado() -> bool:
    """Comprueba si las credenciales mínimas de Notion (Token y Database ID) están configuradas."""
    token = obtener_credencial("NOTION_TOKEN")
    db_id = obtener_credencial("NOTION_DATABASE_ID")
    return bool(token and db_id)


def _trocear_cadena(s: str, limite: int = 2000) -> List[str]:
    """Divide un texto en segmentos que no superen el límite de caracteres de Notion."""
    if not s:
        return [""]
    return [s[i:i + limite] for i in range(0, len(s), limite)]


def crear_rich_text(texto: str) -> list:
    """Parsea negritas (**bold**) y código (`inline`) a la estructura rich_text de Notion.

    Garantiza que ningún fragmento supere los 2000 caracteres (límite estricto de Notion).
    """
    patron = r"(\*\*.*?\*\*|`.*?`)"
    fragmentos = re.split(patron, texto)
    rich_text = []

    for frag in fragmentos:
        if not frag:
            continue
        if frag.startswith("**") and frag.endswith("**"):
            contenido = frag[2:-2]
            for trozo in _trocear_cadena(contenido, 2000):
                rich_text.append({
                    "type": "text",
                    "text": {"content": trozo},
                    "annotations": {"bold": True}
                })
        elif frag.startswith("`") and frag.endswith("`"):
            contenido = frag[1:-1]
            for trozo in _trocear_cadena(contenido, 2000):
                rich_text.append({
                    "type": "text",
                    "text": {"content": trozo},
                    "annotations": {"code": True}
                })
        else:
            for trozo in _trocear_cadena(frag, 2000):
                rich_text.append({
                    "type": "text",
                    "text": {"content": trozo}
                })

    return rich_text if rich_text else [{"type": "text", "text": {"content": texto[:2000]}}]


def markdown_a_bloques_notion(markdown_texto: str, materia: str = "", clase: str = "") -> list:
    bloques = []

    # 1. Cabecera limpia y estilizada
    materia_fmt = materia.replace("_", " ")
    clase_fmt = clase.replace("_", " ")

    bloques.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": crear_rich_text(
                f"**{materia_fmt}** — {clase_fmt}\n"
                f"Sintetizado localmente con Qwen 2.5 7B (Multiplataforma)"
            ),
            "icon": {"type": "emoji", "emoji": "💻"},
            "color": "gray_background"
        }
    })

    # 2. Índice nativo interactivo (Notion añade su propio título en la interfaz)
    bloques.append({
        "object": "block",
        "type": "table_of_contents",
        "table_of_contents": {"color": "gray"}
    })
    bloques.append({"object": "block", "type": "divider", "divider": {}})

    # 3. Parseo y saneamiento de encabezados
    lineas = markdown_texto.split("\n")
    i = 0

    PATRONES_MECANICOS = [
        r"términos?\s*clave",
        r"bloque\s*\d+",
        r"fragmento\s*\d+",
        r"sección\s*\d+"
    ]
    SECCIONES_TOGGLE = ["glosario", "preparación para examen", "checklist", "preguntas de repaso", "chuleta"]

    while i < len(lineas):
        linea = lineas[i].strip()

        if not linea:
            i += 1
            continue

        # Evitar H1 duplicados
        if linea.startswith("# "):
            i += 1
            continue

        # Separador horizontal
        if linea.startswith("---"):
            bloques.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # Detección de títulos H2 o H3
        if linea.startswith(("## ", "### ")):
            es_h2 = linea.startswith("## ")
            texto_encabezado = linea[3 if es_h2 else 4:].strip()
            texto_lower = texto_encabezado.lower()

            es_mecanico = any(re.search(pat, texto_lower) for pat in PATRONES_MECANICOS)
            es_seccion_repaso = any(sec in texto_lower for sec in SECCIONES_TOGGLE)

            if es_mecanico or es_seccion_repaso:
                color_toggle = "blue_background" if es_seccion_repaso else "gray_background"
                bloques.append({
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": crear_rich_text(f"📁 {texto_encabezado}"),
                        "color": color_toggle
                    }
                })
            elif es_h2:
                bloques.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": crear_rich_text(texto_encabezado),
                        "color": "default"
                    }
                })
            else:
                bloques.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": crear_rich_text(texto_encabezado),
                        "color": "default"
                    }
                })
            i += 1
            continue

        # Callouts (> 📌, > ⚠️, > ❌)
        if linea.startswith(">"):
            contenido_cita = linea.lstrip("> ").strip()
            icono = "💡"
            color_fondo = "gray_background"

            if "📌" in contenido_cita:
                icono = "📌"
                color_fondo = "blue_background"
            elif "⚠️" in contenido_cita:
                icono = "⚠️"
                color_fondo = "orange_background"
            elif "❌" in contenido_cita or "🚫" in contenido_cita:
                icono = "🚫"
                color_fondo = "red_background"

            bloques.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": crear_rich_text(contenido_cita),
                    "icon": {"type": "emoji", "emoji": icono},
                    "color": color_fondo
                }
            })
            i += 1
            continue

        # Checklists interactivas (- [ ] o - [x])
        if linea.startswith(("- [ ]", "- [x]")):
            checked = linea.startswith("- [x]")
            bloques.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": crear_rich_text(linea[5:].strip()),
                    "checked": checked
                }
            })
            i += 1
            continue

        # Viñetas normales
        if linea.startswith(("- ", "* ")):
            bloques.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": crear_rich_text(linea[2:].strip())}
            })
            i += 1
            continue

        # Bloques de código multilínea
        if linea.startswith("```"):
            lenguaje = linea[3:].strip().lower() or "javascript"
            lineas_codigo = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                lineas_codigo.append(lineas[i])
                i += 1

            codigo_str = "\n".join(lineas_codigo)
            lenguajes_notion = [
                "javascript", "typescript", "python", "html", "css", "sql",
                "bash", "json", "java", "c", "cpp", "c#", "markdown", "plain text"
            ]
            lang_final = lenguaje if lenguaje in lenguajes_notion else "plain text"
            trozos_codigo = _trocear_cadena(codigo_str, 2000)

            bloques.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": t}} for t in trozos_codigo],
                    "language": lang_final
                }
            })
            i += 1
            continue

        # Párrafos regulares
        bloques.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": crear_rich_text(linea)}
        })
        i += 1

    return bloques


def _peticion_notion_con_reintentos(
    metodo: str,
    url: str,
    headers: dict,
    json_data: Optional[dict] = None,
    max_reintentos: int = 4,
) -> requests.Response:
    """Ejecuta una petición a la API de Notion con manejo robusto de Rate Limit (429)

    y diagnóstico explícito de errores de validación (400).
    """
    for intento in range(1, max_reintentos + 1):
        try:
            kwargs = {"json": json_data} if json_data is not None else {}
            resp = requests.request(metodo, url, headers=headers, timeout=30, **kwargs)
        except requests.RequestException as e:
            if intento == max_reintentos:
                logger.error("[NOTION RED] Fallo de conexión tras %d intentos (%s %s): %s", max_reintentos, metodo, url, e)
                raise RuntimeError(f"Error de conexión con la API de Notion: {e}") from e
            espera = 2.0 * intento
            logger.warning("[NOTION RED] Error de conexión: %s. Reintentando en %.1fs (intento %d/%d)...", e, espera, intento, max_reintentos)
            time.sleep(espera)
            continue

        if resp.status_code in (200, 201):
            return resp

        # HTTP 429: Rate limit de Notion
        if resp.status_code == 429:
            retry_after_str = resp.headers.get("Retry-After", "")
            try:
                espera = float(retry_after_str) if retry_after_str else (1.5 * intento)
            except ValueError:
                espera = 1.5 * intento
            espera = max(1.0, espera)
            logger.warning(
                "[NOTION 429 Rate Limit] Límite de tasa alcanzado. Esperando %.1fs antes de reintentar (intento %d/%d)...",
                espera, intento, max_reintentos
            )
            time.sleep(espera)
            continue

        # HTTP 400: Error de validación de estructura o propiedad
        if resp.status_code == 400:
            error_json = {}
            try:
                error_json = resp.json()
            except Exception:
                pass
            codigo_error = error_json.get("code", "validation_error")
            mensaje_error = error_json.get("message", resp.text)
            logger.error(
                "[NOTION 400 Validation Error] Error de validación en Notion (código: '%s'): %s",
                codigo_error, mensaje_error
            )
            raise RuntimeError(f"Error de validación en Notion (HTTP 400 - {codigo_error}): {mensaje_error}")

        # HTTP 5xx: Errores transitorios de servidor
        if resp.status_code >= 500 and intento < max_reintentos:
            espera = 2.0 * intento
            logger.warning(
                "[NOTION %d Server Error] Error interno en Notion. Reintentando en %.1fs (intento %d/%d)...",
                resp.status_code, espera, intento, max_reintentos
            )
            time.sleep(espera)
            continue

        # Otros errores no recuperables (401 Unauthorized, 403 Forbidden, 404 Not Found, etc.)
        logger.error("[NOTION HTTP %d] Respuesta de error de Notion: %s", resp.status_code, resp.text)
        raise RuntimeError(f"Error de API Notion (HTTP {resp.status_code}): {resp.text}")

    raise RuntimeError(f"Fallo en la petición a Notion tras {max_reintentos} intentos ({metodo} {url})")


def obtener_esquema_base_datos(db_id: str, headers: dict) -> Tuple[str, Optional[str]]:
    try:
        resp = _peticion_notion_con_reintentos(
            "GET",
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=headers,
            max_reintentos=2,
        )
        datos = resp.json().get("properties", {})
        columna_titulo = "Name"
        columna_materia = None

        for nombre_prop, detalles in datos.items():
            tipo = detalles.get("type")
            if tipo == "title":
                columna_titulo = nombre_prop
            elif tipo == "select" and nombre_prop.lower() in ("materia", "asignatura", "subject"):
                columna_materia = nombre_prop

        return columna_titulo, columna_materia
    except Exception as exc:
        logger.warning(
            "[NOTION] No se pudo consultar el esquema de la base de datos (%s). Usando esquema por defecto.",
            exc
        )
        return "Name", "Materia"


def exportar_a_notion(titulo_clase: str, materia: str, markdown_texto: str) -> str:
    token = obtener_credencial("NOTION_TOKEN")
    db_id = obtener_credencial("NOTION_DATABASE_ID")

    if not token or not db_id:
        raise ValueError("Faltan NOTION_TOKEN y/o NOTION_DATABASE_ID en secrets o variables de entorno.")

    db_id_limpio = db_id.replace("-", "").strip()

    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    col_titulo, col_materia = obtener_esquema_base_datos(db_id_limpio, headers)

    propiedades = {
        col_titulo: {"title": [{"text": {"content": titulo_clase.replace('_', ' ')}}]}
    }
    if col_materia:
        propiedades[col_materia] = {"select": {"name": materia.replace('_', ' ')}}

    bloques = markdown_a_bloques_notion(markdown_texto, materia=materia, clase=titulo_clase)
    
    # División en lotes de 100 bloques (límite estricto de la API de Notion)
    primer_lote = bloques[:100]
    lotes_adicionales = [bloques[i:i + 100] for i in range(100, len(bloques), 100)]

    logger.info(
        "[NOTION] Creando página '%s' en base de datos con %d bloques iniciales (total: %d)...",
        titulo_clase, len(primer_lote), len(bloques)
    )

    payload_creacion = {
        "parent": {"database_id": db_id_limpio},
        "icon": {"type": "emoji", "emoji": "📖"},
        "properties": propiedades,
        "children": primer_lote
    }

    resp = _peticion_notion_con_reintentos(
        "POST",
        "https://api.notion.com/v1/pages",
        headers=headers,
        json_data=payload_creacion
    )

    datos_pagina = resp.json()
    page_id = datos_pagina["id"]
    url_pagina = datos_pagina.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    # Enviar lotes adicionales de forma paginada (máximo 100 bloques por petición)
    if lotes_adicionales:
        url_append = f"https://api.notion.com/v1/blocks/{page_id}/children"
        total_lotes = len(lotes_adicionales) + 1
        for num_lote, lote in enumerate(lotes_adicionales, start=2):
            logger.info(
                "[NOTION] Enviando lote adicional %d/%d (%d bloques)...",
                num_lote, total_lotes, len(lote)
            )
            _peticion_notion_con_reintentos(
                "PATCH",
                url_append,
                headers=headers,
                json_data={"children": lote}
            )

    logger.info("[NOTION] Exportación exitosa a Notion: %s", url_pagina)
    return url_pagina