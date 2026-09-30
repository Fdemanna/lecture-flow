"""Módulo de procesamiento por lotes: cola secuencial, métricas y dashboard de ejecución."""
import os
from pathlib import Path
import time
from typing import Optional, Dict
import streamlit as st

from src.cola_manager import (
    ColaManager,
    obtener_ruta_cola,
    ESTADO_PENDIENTE,
    ESTADO_EN_PROGRESO,
    ESTADO_COMPLETADO as COLA_COMPLETADO,
    ESTADO_ERROR,
)
from src.orchestrator import PipelineOrchestrator, normalizar_nombre
from src.downloader import es_url_remota
from src.notificador import notificar_lote_completado
from views.estilos import render_terminal_topbar
from views.sidebar import MAPEO_ASIGNATURAS


def renderizar_vista_lotes(
    root_dir: Path,
    cola_manager: Optional[ColaManager] = None,
    orquestador: Optional[PipelineOrchestrator] = None,
    mapeo_asignaturas: Optional[Dict[str, str]] = None,
) -> None:
    """Renderiza el dashboard de cola de procesamiento por lotes."""
    mapeo = mapeo_asignaturas or MAPEO_ASIGNATURAS
    carpeta_base = root_dir / "clases"
    carpeta_base.mkdir(parents=True, exist_ok=True)
    carpeta_base_str = str(carpeta_base)

    if cola_manager is None:
        cola_path = str(obtener_ruta_cola(str(root_dir)))
        cola = ColaManager(cola_path)
    else:
        cola = cola_manager

    if not st.session_state.get("cola_ejecutando"):
        cola.reconciliar_trabajos_huerfanos()

    trabajos_actuales = cola.listar_trabajos()
    pendientes_previos = [t for t in trabajos_actuales if t["estado"] in (ESTADO_PENDIENTE, ESTADO_EN_PROGRESO)]

    st.markdown("#### 📦 Procesamiento por Lotes")
    st.caption("Encola múltiples grabaciones y procésalas de forma secuencial sin intervención manual.")

    if pendientes_previos and not st.session_state.get("cola_ejecutando"):
        st.warning(
            f"**Cola pendiente detectada.** Hay {len(pendientes_previos)} trabajo(s) sin completar "
            f"de una sesión anterior."
        )
        col_reanudar, col_descartar = st.columns(2)
        with col_reanudar:
            if st.button("▶ Reanudar cola anterior", use_container_width=True, type="primary", key="btn_reanudar_cola"):
                st.session_state["cola_ejecutando"] = True
                st.rerun()
        with col_descartar:
            if st.button("🗑 Descartar cola y empezar de nuevo", use_container_width=True, key="btn_descartar_cola"):
                cola.purgar_cola()
                st.session_state["cola_ejecutando"] = False
                st.rerun()
        st.divider()

    # Formulario multi-archivo y adición a cola
    with st.expander("➕ Añadir archivos a la cola", expanded=not bool(pendientes_previos)):
        col_lotes_f1, col_lotes_f2 = st.columns(2)
        with col_lotes_f1:
            mat_lotes_opts = [k for k in mapeo.keys() if k != "Otra"]
            mats_carpetas = sorted([
                d for d in os.listdir(carpeta_base_str)
                if (carpeta_base / d).is_dir()
            ])
            mats_uniq = list(dict.fromkeys(mat_lotes_opts + mats_carpetas))
            opcion_nueva_l = "➕ Nueva asignatura..."
            mats_uniq.append(opcion_nueva_l)
            sel_mat_lotes = st.selectbox(
                "Asignatura:",
                mats_uniq,
                format_func=lambda x: x if x == opcion_nueva_l else mapeo.get(x, x.replace("_", " ")),
                key="sb_mat_lotes",
            )
            if sel_mat_lotes == opcion_nueva_l:
                mat_lotes_nombre = st.text_input("Nombre nueva asignatura:", key="txt_mat_lotes_nueva").strip()
            else:
                mat_lotes_nombre = sel_mat_lotes

        with col_lotes_f2:
            prefijo_clase = st.text_input(
                "Prefijo de clase (opcional):",
                placeholder="Ej: Tema_01 — si se deja vacío usa el nombre del archivo",
                key="txt_prefijo_clase_lotes",
            ).strip()

        archivos_lotes = st.file_uploader(
            "Selecciona uno o varios archivos de vídeo/audio:",
            type=["mp4", "mkv", "mp3", "m4a", "wav", "mov"],
            accept_multiple_files=True,
            key="fu_lotes",
        )

        if st.button("Añadir archivos a la cola", use_container_width=True, type="primary", key="btn_add_cola", disabled=not archivos_lotes):
            if not mat_lotes_nombre:
                st.error("Indica el nombre de la asignatura antes de añadir a la cola.")
            else:
                mat_seg = normalizar_nombre(mat_lotes_nombre)
                entradas_nuevas = []
                for arch in archivos_lotes:
                    nombre_clase_raw = prefijo_clase if prefijo_clase else Path(arch.name).stem
                    cla_seg = normalizar_nombre(nombre_clase_raw)
                    dir_clase = carpeta_base / mat_seg / cla_seg
                    dir_clase.mkdir(parents=True, exist_ok=True)
                    fichero_seg = normalizar_nombre(arch.name)
                    ruta_destino = dir_clase / fichero_seg
                    with open(str(ruta_destino), "wb") as fh:
                        fh.write(arch.getbuffer())
                    entradas_nuevas.append({
                        "video_path": str(ruta_destino),
                        "materia": mat_seg,
                        "nombre_clase": cla_seg,
                        "directorio_clase": str(dir_clase),
                    })
                agregados = cola.agregar_trabajos(entradas_nuevas)
                st.success(f"Se añadieron {len(agregados)} trabajo(s) a la cola.")
                st.rerun()

        # — Bloque de URLs en masa —
        st.divider()
        st.markdown("**🔗 Añadir múltiples URLs** (una por línea)")
        st.caption("Compatible con YouTube, Blackboard Collaborate, Panopto, Vimeo y cualquier plataforma soportada por yt-dlp.")
        urls_texto = st.text_area(
            "URLs de clases remotas:",
            placeholder="https://www.youtube.com/watch?v=xxx\nhttps://panopto.universidad.es/...\nhttps://blackboard.ejemplo.com/...",
            height=120,
            key="ta_urls_lotes",
        )
        if st.button("🔗 Añadir URLs a la cola", use_container_width=True, key="btn_add_urls_cola", disabled=not urls_texto.strip()):
            if not mat_lotes_nombre:
                st.error("Indica el nombre de la asignatura antes de añadir URLs a la cola.")
            else:
                mat_seg = normalizar_nombre(mat_lotes_nombre)
                urls_validas = [
                    u.strip() for u in urls_texto.strip().splitlines()
                    if u.strip() and es_url_remota(u.strip())
                ]
                urls_invalidas = [
                    u.strip() for u in urls_texto.strip().splitlines()
                    if u.strip() and not es_url_remota(u.strip())
                ]
                if urls_invalidas:
                    st.warning(
                        f"⚠️ Se ignoraron {len(urls_invalidas)} línea(s) que no parecen URL válidas: "
                        + ", ".join(f"`{u[:40]}`" for u in urls_invalidas[:3])
                    )
                if not urls_validas:
                    st.error("No se encontraron URLs válidas. Asegúrate de que comiencen por http:// o https://")
                else:
                    entradas_url = []
                    for idx_url, url_entry in enumerate(urls_validas, start=1):
                        prefijo_raw = prefijo_clase if prefijo_clase else f"clase_url_{idx_url:02d}"
                        cla_seg = normalizar_nombre(prefijo_raw)
                        dir_clase = carpeta_base / mat_seg / cla_seg
                        dir_clase.mkdir(parents=True, exist_ok=True)
                        entradas_url.append({
                            "video_path": url_entry,   # El orquestador detectará la URL
                            "materia": mat_seg,
                            "nombre_clase": cla_seg,
                            "directorio_clase": str(dir_clase),
                        })
                    agregados_url = cola.agregar_trabajos(entradas_url)
                    st.success(f"✅ Se añadieron {len(agregados_url)} URL(s) a la cola.")
                    st.rerun()

    # Panel de métricas y tabla de cola actual
    trabajos_tabla = cola.listar_trabajos()
    st.markdown("##### Estado de la cola")

    badges_html = {
        ESTADO_PENDIENTE:    '<span style="background:#1e3a5f;color:#7ab3ef;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;">Pendiente</span>',
        ESTADO_EN_PROGRESO:  '<span style="background:#3a2e00;color:#f0c040;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;">Procesando</span>',
        COLA_COMPLETADO:     '<span style="background:#0d2e1f;color:#4edea3;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;">Completado</span>',
        ESTADO_ERROR:        '<span style="background:#2e0d0d;color:#e05c5c;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;">Error</span>',
    }

    if trabajos_tabla:
        conteo = cola.conteo_por_estado()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pendientes", conteo[ESTADO_PENDIENTE])
        c2.metric("En progreso", conteo[ESTADO_EN_PROGRESO])
        c3.metric("Completados", conteo[COLA_COMPLETADO])
        c4.metric("Errores", conteo[ESTADO_ERROR])
        st.write("")

        for idx, t in enumerate(trabajos_tabla):
            badge = badges_html.get(t["estado"], badges_html[ESTADO_PENDIENTE])
            nombre_display = t["nombre_clase"].replace("_", " ")
            mat_display = t["materia"].replace("_", " ")
            video_base = Path(t["video_path"]).name
            with st.container():
                tc1, tc2, tc3 = st.columns([3, 2, 1])
                with tc1:
                    st.markdown(f"**{idx + 1}. {nombre_display}** · `{mat_display}`")
                    st.caption(f"📁 {video_base}")
                with tc2:
                    st.html(badge)
                    if t.get("error_msg"):
                        st.caption(f"⚠️ {t['error_msg'][:80]}")
                    if t.get("completado_en"):
                        ts_done = t["completado_en"][:16].replace("T", " ")
                        st.caption(f"✓ {ts_done} UTC")
                with tc3:
                    if t["estado"] == ESTADO_ERROR:
                        if st.button("↩ Reintentar", key=f"btn_retry_{t['id']}", use_container_width=True):
                            cola.actualizar_estado(t["id"], ESTADO_PENDIENTE)
                            st.rerun()
            st.divider()

        col_acciones1, col_acciones2 = st.columns(2)
        with col_acciones1:
            if st.button("🗑 Limpiar completados", use_container_width=True, key="btn_limpiar_cola"):
                n = cola.limpiar_completados()
                st.success(f"Se eliminaron {n} trabajo(s) completados.")
                st.rerun()
        with col_acciones2:
            n_errores = conteo.get(ESTADO_ERROR, 0)
            if st.button(f"↩ Reintentar errores ({n_errores})", use_container_width=True, key="btn_retry_all", disabled=n_errores == 0):
                cola.reintentar_errores()
                st.rerun()
    else:
        st.info("La cola está vacía. Añade archivos usando el formulario superior.")

    # Botón Iniciar Cola
    hay_pendientes = cola.hay_pendientes()
    st.write("")
    col_iniciar_c, col_iniciar_m, col_iniciar_r = st.columns([1, 2, 1])
    with col_iniciar_m:
        btn_iniciar_cola = st.button(
            "🚀 Iniciar Cola",
            use_container_width=True,
            type="primary",
            disabled=not hay_pendientes or st.session_state.get("cola_ejecutando"),
            key="btn_iniciar_cola_main",
        )

    # Bucle visual de ejecución secuencial y terminal en tiempo real
    if btn_iniciar_cola or st.session_state.get("cola_ejecutando"):
        st.session_state["cola_ejecutando"] = True

        total = sum(1 for t in cola.listar_trabajos() if t["estado"] in (ESTADO_PENDIENTE, ESTADO_EN_PROGRESO))
        procesados = 0

        if total == 0:
            st.session_state["cola_ejecutando"] = False
            st.info("No hay trabajos pendientes en la cola.")
        else:
            barra_cola = st.progress(0, text="Iniciando cola de procesamiento...")
            render_terminal_topbar("stdout — batch_pipeline")
            consola_lotes = st.empty()
            estado_lotes = st.status("Procesando cola...", expanded=True)

            lineas_lotes = []

            def cb_progreso_lotes(fase: str, pct: int, msg: str):
                estado_lotes.update(
                    label=f"[{procesados}/{total}] ({fase.upper()}) {msg}",
                    state="running",
                )

            def cb_linea_lotes(linea: str):
                lineas_lotes.append(linea)
                consola_lotes.code("".join(lineas_lotes[-8:]), language="bash")

            if orquestador is None:
                orq = PipelineOrchestrator(
                    callback_progreso=cb_progreso_lotes,
                    callback_linea=cb_linea_lotes,
                )
            else:
                orq = orquestador
                orq.callback_progreso = cb_progreso_lotes
                orq.callback_linea = cb_linea_lotes

            while True:
                siguiente = cola.obtener_siguiente_pendiente()
                if siguiente is None:
                    break

                procesados += 1
                pct_inicio = int((procesados - 1) / total * 100)
                pct_fin = int(procesados / total * 100)
                barra_cola.progress(
                    pct_inicio,
                    text=f"Procesando {procesados}/{total}: {siguiente['nombre_clase'].replace('_', ' ')}",
                )

                ok = orq.procesar_trabajo_cola(
                    trabajo=siguiente,
                    exportar_notion=False,
                    cola_manager=cola,
                )

                if ok:
                    barra_cola.progress(pct_fin, text=f"Completado {procesados}/{total}")
                else:
                    estado_lotes.update(
                        label=f"Error en trabajo {procesados}/{total}: {siguiente['nombre_clase']}",
                        state="error",
                    )
                    st.warning(f"⚠️ Error en trabajo **{siguiente['nombre_clase']}**. Continuando con el siguiente trabajo.")

                time.sleep(1)

            barra_cola.progress(100, text="Cola completada.")
            estado_lotes.update(label="✅ Cola de procesamiento finalizada.", state="complete", expanded=False)
            st.session_state["cola_ejecutando"] = False
            exitosos_lotes = sum(1 for t in cola.listar_trabajos() if t["estado"] == COLA_COMPLETADO)
            errores_lotes = sum(1 for t in cola.listar_trabajos() if t["estado"] == ESTADO_ERROR)
            notificar_lote_completado(
                total=procesados,
                exitosos=exitosos_lotes,
                errores=errores_lotes,
            )
            st.balloons()
            st.success(f"Se procesaron {procesados} clase(s). Revisa la barra lateral para acceder a los apuntes.")
