"""Módulo de visor y editor de apuntes, auditoría determinista y exportación a Notion."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import streamlit as st

from src.notion_exporter import exportar_a_notion
from src.auditor import auditar_apuntes
from src.orchestrator import normalizar_nombre, es_ruta_segura

TIMEOUT_SEGUNDOS = 14400  # 4 horas para clases largas


def _ejecutar_subproceso_con_spinner(
    cmd: list,
    spinner_msg: str,
    exito_msg: str,
    error_prefix: str = "Error en el subproceso",
) -> bool:
    """Ejecuta un comando en subproceso mostrando un spinner interactivo."""
    with st.spinner(spinner_msg):
        try:
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEGUNDOS,
            )
            if resultado.returncode != 0:
                st.error(f"{error_prefix}:\n```\n{resultado.stderr[-2000:]}\n```")
                return False
            st.success(exito_msg)
            return True
        except subprocess.TimeoutExpired:
            st.error("Tiempo de espera agotado. El proceso tardó demasiado.")
            return False
        except Exception as exc:
            st.error(f"{error_prefix}: {exc}")
            return False


def renderizar_editor_apuntes(directorio_clase: Path) -> None:
    """Renderiza el visor/editor de apuntes con backups, re-auditoría y exportación a Notion.

    Parámetros
    ----------
    directorio_clase:
        Path absoluto o relativo a la carpeta de la clase (ej: clases/Materia/Clase_01).
    """
    if not isinstance(directorio_clase, Path):
        directorio_clase = Path(directorio_clase)

    if not directorio_clase.exists():
        st.session_state["clase_seleccionada"] = None
        st.session_state["materia_seleccionada"] = None
        st.warning(f"El directorio especificado no existe: {directorio_clase}")
        st.rerun()

    cla = directorio_clase.name
    mat = directorio_clase.parent.name
    root_dir = directorio_clase.parent.parent.parent  # clases/ -> root_dir

    apuntes_path = directorio_clase / "apuntes.md"
    bak_path = directorio_clase / "apuntes.md.bak"
    transcripcion_path = directorio_clase / "transcripcion.txt"

    col_tit, col_notion, col_btn = st.columns([3, 1, 1])
    with col_tit:
        st.title(f"📖 {cla.replace('_', ' ')}")
        st.caption(f"Asignatura: **{mat.replace('_', ' ')}** · Directorio: `{directorio_clase.name}`")

    with col_notion:
        if apuntes_path.exists():
            if st.button("🚀 Re-exportar a Notion", use_container_width=True, type="primary", key="btn_notion_top"):
                with st.spinner("Sincronizando con Notion..."):
                    try:
                        with open(apuntes_path, "r", encoding="utf-8") as f:
                            texto_md = f.read()
                        url_notion = exportar_a_notion(cla, mat, texto_md)
                        st.success("¡Exportado a Notion con éxito!")
                        st.markdown(f"[🔗 Abrir en Notion]({url_notion})")
                    except Exception as err:
                        st.error(f"Error al exportar a Notion: {err}")

    with col_btn:
        if st.button("⬅️ Nueva Clase", use_container_width=True, key="btn_volver_editor"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.rerun()

    carpeta_clases = directorio_clase.parent.parent

    # =========================================================================
    # GESTIÓN GRANULAR DE LA CLASE (Renombrar, Mover y Eliminar)
    # =========================================================================
    with st.expander("⚙️ Gestión de la clase", expanded=False):
        tab_renombrar, tab_mover, tab_eliminar = st.tabs([
            "✏️ Renombrar",
            "📁 Mover de Asignatura",
            "🗑️ Eliminar Clase",
        ])

        with tab_renombrar:
            st.markdown("##### Renombrar esta clase")
            nombre_actual_legible = cla.replace("_", " ")
            nuevo_nombre_input = st.text_input(
                "Nuevo nombre para la clase:",
                value=nombre_actual_legible,
                key="txt_renombrar_clase_input",
            ).strip()

            if st.button("Guardar nuevo nombre", use_container_width=True, key="btn_renombrar_clase_accion"):
                caracteres_prohibidos = [c for c in r'/\:*?"<>|' if c in nuevo_nombre_input]
                if caracteres_prohibidos:
                    st.error(f"⚠️ El nombre contiene caracteres prohibidos: {' '.join(caracteres_prohibidos)}")
                else:
                    nuevo_slug = normalizar_nombre(nuevo_nombre_input)
                    if not nuevo_slug:
                        st.error("⚠️ El nombre de la clase no puede estar vacío.")
                    elif nuevo_slug == cla:
                        st.info("El nombre indicado es idéntico al actual.")
                    else:
                        carpeta_asignatura = directorio_clase.parent
                        nuevo_dir_clase = carpeta_asignatura / nuevo_slug
                        if not es_ruta_segura(nuevo_dir_clase, base=carpeta_clases):
                            st.error("⚠️ La ruta de destino no es segura.")
                        elif nuevo_dir_clase.exists():
                            st.error(f"⚠️ Ya existe una clase llamada '{nuevo_slug}' en la asignatura '{mat.replace('_', ' ')}'.")
                        else:
                            try:
                                shutil.move(str(directorio_clase), str(nuevo_dir_clase))
                                st.session_state["clase_seleccionada"] = nuevo_slug
                                st.success("✅ Clase renombrada correctamente.")
                                time.sleep(0.5)
                                st.rerun()
                            except OSError as err:
                                st.error(f"Error al renombrar el directorio: {err}")

        with tab_mover:
            st.markdown("##### Mover clase a otra asignatura")
            if carpeta_clases.exists():
                otras_materias = sorted([
                    d.name for d in carpeta_clases.iterdir()
                    if d.is_dir() and not d.name.startswith(".") and d.name != mat
                ])
            else:
                otras_materias = []

            opcion_nueva_m = "➕ Mover a nueva asignatura..."
            opciones_destino = otras_materias + [opcion_nueva_m]

            mat_destino_sel = st.selectbox(
                "Selecciona la asignatura de destino:",
                opciones_destino,
                format_func=lambda x: x if x == opcion_nueva_m else x.replace("_", " "),
                key="sb_mover_asignatura_sel",
            )

            if mat_destino_sel == opcion_nueva_m:
                nueva_mat_nombre = st.text_input(
                    "Nombre de la nueva asignatura:",
                    placeholder="Ej: Programación Web",
                    key="txt_nueva_mat_mover",
                ).strip()
                caracteres_prohibidos_mat = [c for c in r'/\:*?"<>|' if c in nueva_mat_nombre]
                mat_destino_slug = normalizar_nombre(nueva_mat_nombre) if nueva_mat_nombre else ""
            else:
                caracteres_prohibidos_mat = []
                mat_destino_slug = mat_destino_sel

            if st.button("Mover clase a la asignatura seleccionada", use_container_width=True, key="btn_mover_clase_accion"):
                if caracteres_prohibidos_mat:
                    st.error(f"⚠️ El nombre contiene caracteres prohibidos: {' '.join(caracteres_prohibidos_mat)}")
                elif not mat_destino_slug:
                    st.error("⚠️ Debes seleccionar o especificar la asignatura de destino.")
                elif mat_destino_slug == mat:
                    st.warning("La clase ya pertenece a esa asignatura.")
                else:
                    dir_nueva_materia = carpeta_clases / mat_destino_slug
                    destino_final = dir_nueva_materia / cla
                    if not es_ruta_segura(destino_final, base=carpeta_clases):
                        st.error("⚠️ La ruta de destino no es segura.")
                    elif destino_final.exists():
                        st.error(f"⚠️ Ya existe una clase con el nombre '{cla}' en la asignatura '{mat_destino_slug.replace('_', ' ')}'.")
                    else:
                        try:
                            dir_nueva_materia.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(directorio_clase), str(destino_final))
                            st.session_state["materia_seleccionada"] = mat_destino_slug
                            st.session_state["clase_seleccionada"] = cla
                            st.success(f"✅ Clase movida con éxito a '{mat_destino_slug.replace('_', ' ')}'.")
                            time.sleep(0.5)
                            st.rerun()
                        except OSError as err:
                            st.error(f"Error al mover la clase: {err}")

        with tab_eliminar:
            st.markdown("##### Eliminar clase permanentemente")
            st.warning(
                f"⚠️ Esta acción eliminará permanentemente la carpeta **{cla.replace('_', ' ')}** "
                f"incluyendo todos los apuntes, audios y transcripciones generadas."
            )
            confirmacion_eliminar = st.checkbox(
                "Confirmo que deseo eliminar definitivamente esta clase y sus archivos.",
                key="chk_confirmar_eliminar_clase",
            )
            if st.button(
                "🗑️ Eliminar esta clase",
                type="primary",
                disabled=not confirmacion_eliminar,
                use_container_width=True,
                key="btn_eliminar_clase_definitivo",
            ):
                try:
                    shutil.rmtree(str(directorio_clase))
                    st.session_state["clase_seleccionada"] = None
                    st.success("✅ Clase eliminada.")
                    time.sleep(0.5)
                    st.rerun()
                except OSError as err:
                    st.error(f"Error al eliminar la clase: {err}")

    # Reprocesamiento granular
    tiene_transcripcion = (
        transcripcion_path.exists()
        and transcripcion_path.stat().st_size > 0
    )

    _EXTS_MEDIA = (".mp4", ".mkv", ".mov", ".avi", ".mp3", ".m4a", ".wav")
    _archivo_media = next(
        (
            directorio_clase / f
            for f in os.listdir(str(directorio_clase))
            if f.lower().endswith(_EXTS_MEDIA)
        ),
        None,
    )

    with st.expander("🔧 Reprocesar esta clase", expanded=False):
        col_re1, col_re2 = st.columns(2)

        with col_re1:
            btn_solo_apuntes = st.button(
                "🔄 Re-generar Apuntes (Solo Síntesis)",
                key="btn_solo_apuntes",
                use_container_width=True,
                disabled=not tiene_transcripcion,
                help="Regenera los apuntes usando la transcripción existente. Se omite la re-transcripción.",
            )
            if not tiene_transcripcion:
                st.caption("⚠️ Sin transcripción disponible — ejecuta primero el pipeline completo.")

        with col_re2:
            btn_forzar = st.button(
                "⚠️ Re-transcribir desde audio",
                key="btn_forzar_transcripcion",
                use_container_width=True,
                disabled=_archivo_media is None,
                help="Vuelve a ejecutar Whisper desde el audio guardado y regenera los apuntes completos.",
            )
            if _archivo_media is None:
                st.caption("⚠️ No se encontró archivo multimedia en la carpeta de la clase.")

        script_procesar = root_dir / "src" / "procesar_clase.py"
        if not script_procesar.exists():
            # Fallback en caso de rutas relativas
            script_procesar = Path("src/procesar_clase.py").resolve()

        if btn_solo_apuntes:
            cmd_solo = [
                sys.executable, "-u",
                str(script_procesar),
                mat, cla, "",
                "--solo-apuntes",
            ]
            ok = _ejecutar_subproceso_con_spinner(
                cmd_solo,
                spinner_msg="Re-sintetizando apuntes y auditando...",
                exito_msg="✅ Apuntes regenerados correctamente.",
                error_prefix="Error en la re-generación de apuntes",
            )
            if ok:
                st.rerun()

        if btn_forzar:
            if "confirmar_retranscribir" not in st.session_state:
                st.session_state["confirmar_retranscribir"] = False

            if not st.session_state["confirmar_retranscribir"]:
                st.warning(
                    "⚠️ **Esto sobrescribirá la transcripción y los apuntes existentes.** "
                    "Pulsa de nuevo el botón para confirmar."
                )
                st.session_state["confirmar_retranscribir"] = True
            else:
                st.session_state["confirmar_retranscribir"] = False
                cmd_forzar = [
                    sys.executable, "-u",
                    str(script_procesar),
                    mat, cla, str(_archivo_media or ""),
                    "--forzar-transcripcion",
                ]
                ok2 = _ejecutar_subproceso_con_spinner(
                    cmd_forzar,
                    spinner_msg="Re-transcribiendo con Whisper y regenerando apuntes...",
                    exito_msg="✅ Re-transcripción y apuntes completados.",
                    error_prefix="Error en la re-transcripción",
                )
                if ok2:
                    st.rerun()

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📝 Apuntes y Ejemplos", "🔍 Revisión y Auditoría", "📜 Transcripción Cruda"])

    with tab1:
        if apuntes_path.exists():
            with open(apuntes_path, "r", encoding="utf-8") as f:
                contenido_actual = f.read()

            col_modo, col_bak_info = st.columns([2, 3])
            with col_modo:
                modo_edicion = st.checkbox("✏️ Modo edición en caliente (Markdown)", key="chk_modo_edicion")
            with col_bak_info:
                if bak_path.exists():
                    st.caption(f"🛡️ Backup previo disponible: `{bak_path.name}`")

            if modo_edicion:
                contenido_editado = st.text_area(
                    "Editor de Apuntes:",
                    value=contenido_actual,
                    height=520,
                    key="txt_editor_apuntes"
                )
                col_save, col_restore = st.columns([2, 2])
                with col_save:
                    if st.button("💾 Guardar Cambios (Crea .bak)", type="primary", key="btn_guardar_apuntes"):
                        try:
                            # 1. Crear backup previo (.bak)
                            shutil.copy2(apuntes_path, bak_path)
                            # 2. Guardar contenido nuevo
                            with open(apuntes_path, "w", encoding="utf-8") as f:
                                f.write(contenido_editado)
                            st.success("✅ Cambios guardados correctamente y backup (.bak) actualizado.")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar los apuntes: {e}")

                with col_restore:
                    if bak_path.exists():
                        if st.button("↩ Restaurar desde backup (.bak)", key="btn_restaurar_bak"):
                            shutil.copy2(bak_path, apuntes_path)
                            st.success("✅ Apuntes restaurados desde el archivo de backup.")
                            time.sleep(0.5)
                            st.rerun()
            else:
                st.markdown(contenido_actual)
        else:
            st.warning("Apuntes pendientes de generación.")

    with tab2:
        if apuntes_path.exists():
            with open(apuntes_path, "r", encoding="utf-8") as _f:
                _texto_md = _f.read()

            col_audit_btn, _ = st.columns([2, 3])
            with col_audit_btn:
                btn_reauditar = st.button("🔄 Re-auditar apuntes deterministamente", key="btn_reauditar_now")

            if btn_reauditar:
                st.toast("Auditoría determinista ejecutada con éxito.")

            _res = auditar_apuntes(_texto_md)

            # Badge de estado global
            if _res.es_valido:
                st.html("""
                <div style="display:inline-flex;align-items:center;gap:8px;
                            background:#0d2e1f;border:1px solid #4edea3;
                            border-radius:8px;padding:10px 18px;margin-bottom:12px;">
                  <span style="font-size:1.3rem;">✅</span>
                  <span style="color:#4edea3;font-weight:700;">Auditoría superada — sin errores</span>
                </div>""")
            else:
                st.html("""
                <div style="display:inline-flex;align-items:center;gap:8px;
                            background:#2e0d0d;border:1px solid #e05c5c;
                            border-radius:8px;padding:10px 18px;margin-bottom:12px;">
                  <span style="font-size:1.3rem;">❌</span>
                  <span style="color:#e05c5c;font-weight:700;">Auditoría fallida — revisa los errores</span>
                </div>""")

            # Métricas rápidas
            _mc1, _mc2, _mc3 = st.columns(3)
            _mc1.metric("Timestamps", _res.timestamps_detectados)
            _mc2.metric("Cobertura de términos", f"{_res.cobertura_terminos:.0%}")
            _mc3.metric("Discrepancias técnicas", len(_res.errores))

            # Discrepancias técnicas y advertencias
            if _res.errores:
                st.markdown("##### 🔴 Discrepancias técnicas")
                for _err in _res.errores:
                    st.error(_err)

            # Advertencias de sintaxis
            if _res.advertencias:
                st.markdown("##### 🟡 Advertencias de sintaxis")
                for _adv in _res.advertencias:
                    st.warning(_adv)

            if not _res.errores and not _res.advertencias:
                st.success("Los apuntes superaron todas las reglas de validación sin advertencias.")
        else:
            st.info("Genera los apuntes primero para ejecutar la auditoría determinista.")

    with tab3:
        if transcripcion_path.exists():
            with open(transcripcion_path, "r", encoding="utf-8") as f:
                st.text_area("Transcripción:", f.read(), height=450)
