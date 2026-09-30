"""LectureFlow - Enrutador Principal.

Punto de entrada de la aplicación Streamlit modularizada.
"""
import os
from pathlib import Path
import sys
import streamlit as st

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.cola_manager import ColaManager, obtener_ruta_cola
from src.orchestrator import PipelineOrchestrator
from views.estilos import aplicar_estilos, render_header
from views.sidebar import renderizar_sidebar
from views.vista_individual import renderizar_vista_individual
from views.vista_lotes import renderizar_vista_lotes
from views.editor_apuntes import renderizar_editor_apuntes

ROOT_DIR = Path(__file__).resolve().parent

# Configuración inicial de Streamlit
st.set_page_config(
    page_title="LectureFlow - Asistente de Estudio",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Cargar estilos globales y header de cabecera
aplicar_estilos()
render_header()

# 2. Inicialización de estado de sesión
valores_defecto = {
    "clase_seleccionada": None,
    "materia_seleccionada": None,
    "modo_reanudacion": None,
    "directorio_pipeline": None,
    "cola_ejecutando": False,
    "vista_principal": "individual",
}
for clave, valor in valores_defecto.items():
    if clave not in st.session_state:
        st.session_state[clave] = valor

# 3. Reconciliar huérfanos de cola con ColaManager al arrancar
cola_manager = ColaManager(str(obtener_ruta_cola(str(ROOT_DIR))))
if "cola_reconciliada" not in st.session_state:
    cola_manager.reconciliar_trabajos_huerfanos()
    st.session_state["cola_reconciliada"] = True

# 4. Invocar menú lateral
estado_nav = renderizar_sidebar(ROOT_DIR)

# 5. Instanciar orquestador para desacoplamiento y reuso
orquestador = PipelineOrchestrator()

# 6. Despacho dinámico según la navegación
materia_sel = estado_nav.get("materia")
clase_sel = estado_nav.get("clase")

if materia_sel and clase_sel:
    directorio_clase = ROOT_DIR / "clases" / materia_sel / clase_sel
    renderizar_editor_apuntes(directorio_clase)
elif estado_nav.get("vista") == "lotes":
    renderizar_vista_lotes(ROOT_DIR, cola_manager=cola_manager, orquestador=orquestador)
else:
    renderizar_vista_individual(ROOT_DIR, orquestador=orquestador)