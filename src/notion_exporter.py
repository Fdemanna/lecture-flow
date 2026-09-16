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
import re
from typing import Optional, Tuple
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import streamlit as st
except ImportError:
    st = None


def obtener_credencial(clave: str) -> str:
    valor = os.getenv(clave)
    if not valor and st is not None:
        try:
            if hasattr(st, "secrets") and clave in st.secrets:
                valor = str(st.secrets[clave])
        except Exception:
            valor = None
    return valor or ""


def crear_rich_text(texto: str) -> list:
    """Parsea negritas (**bold**) y código (`inline`) a la estructura rich_text de Notion."""
    patron = r"(\*\*.*?\*\*|`.*?`)"
    fragmentos = re.split(patron, texto)
    rich_text = []

    for frag in fragmentos:
        if not frag:
            continue
        if frag.startswith("**") and frag.endswith("**"):
            rich_text.append({
                "type": "text",
                "text": {"content": frag[2:-2][:2000]},
                "annotations": {"bold": True}
            })
        elif frag.startswith("`") and frag.endswith("`"):
            rich_text.append({
                "type": "text",
                "text": {"content": frag[1:-1][:2000]},
                "annotations": {"code": True}
            })
        else:
            rich_text.append({
                "type": "text",
                "text": {"content": frag[:2000]}
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

            bloques.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": codigo_str[:2000]}}],
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


def obtener_esquema_base_datos(db_id: str, headers: dict) -> Tuple[str, Optional[str]]:
    resp = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=headers)
    if resp.status_code != 200:
        return "Name", "Materia"

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
    primer_lote = bloques[:100]
    lotes_adicionales = [bloques[i:i + 100] for i in range(100, len(bloques), 100)]

    payload_creacion = {
        "parent": {"database_id": db_id_limpio},
        "icon": {"type": "emoji", "emoji": "📖"},
        "properties": propiedades,
        "children": primer_lote
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload_creacion)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Error de API Notion ({resp.status_code}): {resp.text}")

    datos_pagina = resp.json()
    page_id = datos_pagina["id"]
    url_pagina = datos_pagina.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    for lote in lotes_adicionales:
        url_append = f"https://api.notion.com/v1/blocks/{page_id}/children"
        resp_append = requests.patch(url_append, headers=headers, json={"children": lote})
        if resp_append.status_code not in (200, 201):
            print(f"Aviso: Falló el envío de un lote secundario: {resp_append.text}")

    return url_pagina