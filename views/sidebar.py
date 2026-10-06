"""Módulo de la barra lateral: explorador de clases, navegación y administración."""
import os
from pathlib import Path
import shutil
import time
from typing import Dict, Any, Optional
import streamlit as st

from src.orchestrator import normalizar_nombre
from src.study_engine import obtener_progreso

# Diccionario dinámico de mapeo (mantenido vacío por compatibilidad hacia atrás)
MAPEO_ASIGNATURAS: Dict[str, str] = {}


def renderizar_sidebar(root_dir: Path, mapeo_asignaturas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Renderiza el menú lateral con navegación, listado de asignaturas y administración.

    Retorna un diccionario con el estado actual de navegación:
        {"vista": str, "materia": Optional[str], "clase": Optional[str]}
    """
    mapeo = mapeo_asignaturas or MAPEO_ASIGNATURAS
    carpeta_base = root_dir / "clases"
    carpeta_base.mkdir(parents=True, exist_ok=True)

    st.sidebar.markdown("### Asignaturas 📚")

    col_sb1, col_sb2 = st.sidebar.columns(2)
    with col_sb1:
        if st.button("➕ Nueva Clase", use_container_width=True, type="primary", key="btn_sb_nueva"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.session_state["vista_actual"] = "individual"
            st.session_state["vista_principal"] = "individual"
            st.rerun()
    with col_sb2:
        if st.button("📦 Por Lotes", use_container_width=True, key="btn_sb_lotes"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.session_state["vista_actual"] = "lotes"
            st.session_state["vista_principal"] = "lotes"
            st.rerun()

    progreso = obtener_progreso()
    racha = progreso.get("racha_actual", 0)
    if st.sidebar.button(f"🎯 Práctica Diaria (🔥 {racha})", use_container_width=True, key="btn_sb_practica"):
        st.session_state["clase_seleccionada"] = None
        st.session_state["materia_seleccionada"] = None
        st.session_state["vista_actual"] = "practica"
        st.session_state["vista_principal"] = "practica"
        st.rerun()

    st.sidebar.divider()

    if carpeta_base.exists():
        materias_existentes = sorted([
            d.name for d in carpeta_base.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])
    else:
        materias_existentes = []

    if materias_existentes:
        for m in materias_existentes:
            label = mapeo.get(m, m.replace('_', ' '))
            with st.sidebar.expander(f"📁 {label}", expanded=True):
                ruta_m = carpeta_base / m
                clases_m = sorted([
                    c.name for c in ruta_m.iterdir()
                    if c.is_dir() and not c.name.startswith(".")
                ])
                if clases_m:
                    for c in clases_m:
                        if st.button(f"📄 {c.replace('_', ' ')}", key=f"btn_{m}_{c}", use_container_width=True):
                            st.session_state["materia_seleccionada"] = m
                            st.session_state["clase_seleccionada"] = c
                            st.session_state["vista_actual"] = None
                            st.rerun()
                else:
                    col_info, col_del = st.columns([3, 1])
                    col_info.caption("Sin clases registradas.")
                    if col_del.button("🗑️", key=f"del_mat_{m}", help="Eliminar carpeta de asignatura"):
                        if ruta_m.exists():
                            shutil.rmtree(ruta_m)
                            if st.session_state.get("materia_seleccionada") == m:
                                st.session_state["materia_seleccionada"] = None
                                st.session_state["clase_seleccionada"] = None
                            st.rerun()
    else:
        st.sidebar.caption("No hay asignaturas creadas.")

    if materias_existentes:
        st.sidebar.divider()
        with st.sidebar.expander("⚙️ Administrar materias", expanded=False):
            tab_renombrar, tab_eliminar = st.tabs(["✏️ Renombrar", "🗑️ Eliminar"])

            # PESTAÑA RENOMBRAR:
            with tab_renombrar:
                materia_origen = st.selectbox(
                    "Materia a renombrar:",
                    materias_existentes,
                    format_func=lambda x: mapeo.get(x, x.replace("_", " ")),
                    key="sb_sel_ren_mat"
                )
                nuevo_nombre_mat = st.text_input(
                    "Nuevo nombre:",
                    value=materia_origen.replace("_", " "),
                    key="sb_txt_ren_mat"
                )
                if st.button("Guardar nombre", key="sb_btn_ren_mat", use_container_width=True):
                    nombre_slug = normalizar_nombre(nuevo_nombre_mat)
                    if nombre_slug and nombre_slug != materia_origen:
                        ruta_antigua = root_dir / "clases" / materia_origen
                        ruta_nueva = root_dir / "clases" / nombre_slug
                        if not ruta_nueva.exists():
                            ruta_antigua.rename(ruta_nueva)
                            if st.session_state.get("materia_seleccionada") == materia_origen:
                                st.session_state["materia_seleccionada"] = nombre_slug
                            st.success("Materia renombrada correctamente.")
                            st.rerun()
                        else:
                            st.error("Ya existe una materia con ese nombre.")

            # PESTAÑA ELIMINAR:
            with tab_eliminar:
                materia_a_borrar = st.selectbox(
                    "Materia a eliminar:",
                    materias_existentes,
                    format_func=lambda x: mapeo.get(x, x.replace("_", " ")),
                    key="sb_sel_del_mat"
                )
                confirmar = st.checkbox(
                    f"Confirmar eliminación de '{materia_a_borrar.replace('_', ' ')}'",
                    key="sb_chk_del_mat"
                )
                if st.button("Eliminar carpeta de materia", type="secondary", disabled=not confirmar, key="sb_btn_del_mat", use_container_width=True):
                    ruta_a_borrar = root_dir / "clases" / materia_a_borrar
                    if ruta_a_borrar.exists():
                        shutil.rmtree(ruta_a_borrar)
                        if st.session_state.get("materia_seleccionada") == materia_a_borrar:
                            st.session_state["materia_seleccionada"] = None
                            st.session_state["clase_seleccionada"] = None
                        st.rerun()

    return {
        "vista": st.session_state.get("vista_actual", st.session_state.get("vista_principal", "individual")),
        "materia": st.session_state.get("materia_seleccionada"),
        "clase": st.session_state.get("clase_seleccionada"),
    }
