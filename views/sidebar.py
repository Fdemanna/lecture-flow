"""Módulo de la barra lateral: explorador de clases, navegación y administración."""
import os
from pathlib import Path
import shutil
import time
from typing import Dict, Any, Optional
import streamlit as st

from src.orchestrator import normalizar_nombre

MAPEO_ASIGNATURAS = {
    "Bases_de_Datos": "Bases de Datos",
    "Programacion": "Programación",
    "Lenguajes_de_Marcas": "Lenguajes de Marcas",
    "Entornos_de_Desarrollo": "Entornos de Desarrollo",
    "Sistemas_Informaticos": "Sistemas Informáticos",
    "FOL": "Formación y Orientación Laboral (FOL)",
    "Otra": "Otra (personalizada)",
}


def renderizar_sidebar(root_dir: Path, mapeo_asignaturas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Renderiza el menú lateral con navegación, listado de asignaturas y administración.

    Retorna un diccionario con el estado actual de navegación:
        {"vista": str, "materia": Optional[str], "clase": Optional[str]}
    """
    mapeo = mapeo_asignaturas or MAPEO_ASIGNATURAS
    carpeta_base = root_dir / "clases"
    carpeta_base.mkdir(parents=True, exist_ok=True)
    carpeta_base_str = str(carpeta_base)

    st.sidebar.markdown("### Asignaturas 📚")

    col_sb1, col_sb2 = st.sidebar.columns(2)
    with col_sb1:
        if st.button("➕ Nueva Clase", use_container_width=True, type="primary", key="btn_sb_nueva"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.session_state["vista_principal"] = "individual"
            st.rerun()
    with col_sb2:
        if st.button("📦 Por Lotes", use_container_width=True, key="btn_sb_lotes"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.session_state["vista_principal"] = "lotes"
            st.rerun()

    st.sidebar.divider()

    materias_existentes = sorted([
        d for d in os.listdir(carpeta_base_str)
        if (carpeta_base / d).is_dir()
    ])

    if materias_existentes:
        for m in materias_existentes:
            label = mapeo.get(m, m.replace('_', ' '))
            with st.sidebar.expander(f"📁 {label}", expanded=True):
                ruta_m = carpeta_base / m
                clases_m = sorted([
                    c for c in os.listdir(str(ruta_m))
                    if (ruta_m / c).is_dir()
                ])
                if clases_m:
                    for c in clases_m:
                        if st.button(f"📄 {c.replace('_', ' ')}", key=f"btn_{m}_{c}", use_container_width=True):
                            st.session_state["materia_seleccionada"] = m
                            st.session_state["clase_seleccionada"] = c
                            st.rerun()
                else:
                    st.caption("Sin clases registradas.")
    else:
        st.sidebar.info("Aquí aparecerán tus asignaturas y clases procesadas.")

    st.sidebar.divider()
    if materias_existentes:
        with st.sidebar.expander("⚙️ Administrar Asignaturas"):
            tab_renombrar, tab_eliminar = st.tabs(["✏️ Renombrar", "🗑️ Eliminar"])

            with tab_renombrar:
                mat_renombrar = st.selectbox(
                    "Materia a renombrar:",
                    materias_existentes,
                    key="sb_renombrar",
                    format_func=lambda x: mapeo.get(x, x.replace('_', ' '))
                )
                nuevo_nombre = st.text_input(
                    "Nuevo nombre para la asignatura:",
                    value=mat_renombrar.replace('_', ' '),
                    key="txt_nuevo_nombre"
                )
                if st.button("Guardar nuevo nombre", use_container_width=True):
                    sanit = normalizar_nombre(nuevo_nombre.strip())
                    if sanit and sanit != mat_renombrar:
                        try:
                            os.rename(
                                str(carpeta_base / mat_renombrar),
                                str(carpeta_base / sanit)
                            )
                            st.sidebar.success("Asignatura renombrada correctamente.")
                            time.sleep(0.5)
                            st.rerun()
                        except OSError as e:
                            st.sidebar.error(f"Error al renombrar: {e}")

            with tab_eliminar:
                mat_eliminar = st.selectbox(
                    "Asignatura a borrar:",
                    materias_existentes,
                    key="sb_eliminar",
                    format_func=lambda x: mapeo.get(x, x.replace('_', ' '))
                )

                ruta_eliminar = carpeta_base / mat_eliminar
                try:
                    elementos = len(os.listdir(str(ruta_eliminar)))
                    st.warning(f"⚠️ Esta carpeta contiene {elementos} elemento(s).")
                except OSError:
                    pass

                confirmacion = st.checkbox("Confirmo que deseo eliminar esta asignatura y todos sus archivos")

                if st.button("Eliminar permanentemente", type="primary", disabled=not confirmacion, use_container_width=True):
                    try:
                        shutil.rmtree(str(ruta_eliminar))
                        st.sidebar.success("Asignatura eliminada.")
                        time.sleep(0.5)
                        st.rerun()
                    except OSError as e:
                        st.sidebar.error(f"Error al eliminar: {e}")

    return {
        "vista": st.session_state.get("vista_principal", "individual"),
        "materia": st.session_state.get("materia_seleccionada"),
        "clase": st.session_state.get("clase_seleccionada"),
    }
